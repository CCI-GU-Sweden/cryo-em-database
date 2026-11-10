"""Authorized, transactional inventory commands for reusable physical boxes."""

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from .permissions import current_staff
from .services import record_audit
from .storage_models import BoxEvent, GridBox, GridBoxType, GridSlot, Puck


def lock_inventory():
    # Six staff and infrequent inventory writes: serialize these short commands
    # to protect capacity and avoid lock-order inversions between source/destination.
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE registry_gridbox IN SHARE ROW EXCLUSIVE MODE")


def destination(puck_id):
    if not puck_id:
        return None
    try:
        puck = Puck.objects.select_related("cane__dewar").get(pk=puck_id)
    except (Puck.DoesNotExist, ValueError, TypeError) as error:
        raise ValidationError("Choose a valid puck.") from error
    if puck.cane.name != "Cane 1" or puck.cane.dewar.name != "Dewar 1":
        raise ValidationError("Choose a puck in Dewar 1 / Cane 1.")
    if GridBox.objects.filter(puck=puck).count() >= 12:
        raise ValidationError("This puck already contains 12 gridboxes.")
    return puck


@transaction.atomic
def register_box(*, actor, name, box_type_id, puck_id=None):
    actor = current_staff(actor)
    lock_inventory()
    name = name.strip()
    if not name:
        raise ValidationError("Enter a gridbox name.")
    if GridBox.objects.filter(name__iexact=name).exists():
        raise ValidationError("That gridbox name is already registered. Select the existing box.")
    try:
        kind = GridBoxType.objects.get(pk=box_type_id)
    except (GridBoxType.DoesNotExist, ValueError, TypeError) as error:
        raise ValidationError("Choose a configured gridbox type.") from error
    box = GridBox(name=name, box_type=kind, puck=destination(puck_id))
    box.full_clean()
    box.save()
    for side, spec in kind.layout.items():
        for position in range(1, spec["capacity"] + 1):
            GridSlot.objects.create(box=box, side=side, position=position)
    BoxEvent.objects.create(
        box=box, actor=actor, operation="registered", to_puck=box.puck, occurred_at=timezone.now()
    )
    record_audit(
        actor, box, "create", {"name": name, "box_type_id": kind.pk, "puck_id": box.puck_id}
    )
    return box


@transaction.atomic
def change_box(
    *,
    actor,
    box_id,
    expected_version,
    action,
    puck_id=None,
    occurred_at=None,
    transfer_destination="",
):
    actor = current_staff(actor)
    lock_inventory()
    box = GridBox.objects.select_for_update().get(pk=box_id)
    if type(expected_version) is not int or box.version != expected_version:
        raise ValidationError("This box changed. Reload before trying again.")
    if box.discarded or box.transferred_at:
        raise ValidationError("Discarded or transferred boxes are read-only.")
    occurred_at = occurred_at or timezone.now()
    if timezone.is_naive(occurred_at):
        raise ValidationError("Enter a transfer time with a timezone.")
    previous = box.puck
    if action == "discard":
        # Lock slots as well: future grid-placement commands must use the same
        # inventory lock before changing occupancy.
        slots = list(box.slots.select_for_update())
        if any(slot.grid_id is not None for slot in slots):
            raise ValidationError("Remove all grids before discarding this box.")
        box.discarded = True
        box.puck = None
    elif action == "transfer":
        transfer_destination = transfer_destination.strip()
        if not transfer_destination:
            raise ValidationError("Enter the receiving laboratory or destination.")
        box.transferred_at = occurred_at
        box.transfer_destination = transfer_destination
        box.puck = None
    elif action == "move":
        if box.puck_id == (int(puck_id) if puck_id else None):
            return box
        box.puck = destination(puck_id)
    else:
        raise ValidationError("Choose a valid box action.")
    box.version += 1
    box.full_clean()
    box.save()
    BoxEvent.objects.create(
        box=box,
        actor=actor,
        operation=action,
        from_puck=previous,
        to_puck=box.puck,
        occurred_at=occurred_at,
        destination=box.transfer_destination,
    )
    record_audit(
        actor,
        box,
        action,
        {
            "from_puck_id": previous.pk if previous else None,
            "to_puck_id": box.puck_id,
            "discarded": box.discarded,
            "transfer_destination": box.transfer_destination,
            "occurred_at": occurred_at.isoformat(),
        },
    )
    return box
