"""Physical placement commands share the inventory lock with box actions."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Grid
from .permissions import require_grid_editor
from .storage import change_box, lock_inventory, sync_puck_locations
from .storage_models import GridEvent, GridSlot


def slot_label(slot):
    if len(slot.box.box_type.layout) > 1:
        return ("C" if slot.side == "clipped" else "U") + str(slot.position)
    return str(slot.position)


def location(grid):
    slot = GridSlot.objects.select_related("box__puck", "box__box_type").filter(grid=grid).first()
    if not slot:
        return "Unknown — needs review"
    box = slot.box
    where = (
        f"Transferred to {box.transfer_destination}"
        if box.transferred_at
        else (f"{box.puck} puck" if box.puck else "Box in stock")
    )
    return f"{where} / {box.name} / Slot {slot_label(slot)}"


@transaction.atomic
def place_grid(*, actor, grid_id, slot_id, clipped, expected_version, occurred_at, puck_id=None):
    lock_inventory()
    grid = Grid.objects.select_for_update().get(pk=grid_id)
    actor = require_grid_editor(actor, grid)
    if type(expected_version) is not int or grid.version != expected_version:
        raise ValidationError("This grid changed. Reload before storing it.")
    if type(clipped) is not bool:
        raise ValidationError("Choose the clipping state.")
    if grid.is_clipped and not clipped:
        raise ValidationError("A clipped grid cannot be made unclipped through storage.")
    if occurred_at is None or timezone.is_naive(occurred_at):
        raise ValidationError("Enter the action date and time.")
    if grid.session.prepared_at and occurred_at < grid.session.prepared_at:
        raise ValidationError("Storage cannot precede the preparation time.")
    current = GridSlot.objects.select_related("box").filter(grid=grid).first()
    if current and current.box.transferred_at:
        raise ValidationError("This grid has left CCI with its box.")
    try:
        slot = GridSlot.objects.select_related("box__box_type", "box__puck").get(pk=slot_id)
    except GridSlot.DoesNotExist as error:
        raise ValidationError("Choose a valid grid slot.") from error
    if slot.box.discarded or slot.box.transferred_at:
        raise ValidationError("Choose an active box in CCI inventory.")
    spec = slot.box.box_type.layout.get(slot.side)
    if not spec or not 1 <= slot.position <= spec["capacity"] or spec["clipped"] != clipped:
        raise ValidationError("This slot is not compatible with the grid clipping state.")
    if slot.grid_id not in (None, grid.pk):
        raise ValidationError("That slot is now occupied. Choose another slot.")
    if current and current.pk == slot.pk and grid.is_clipped == clipped:
        return grid
    latest = grid.physical_events.order_by("-occurred_at").first()
    if latest and occurred_at < latest.occurred_at:
        latest_time = timezone.localtime(latest.occurred_at).strftime("%Y-%m-%d %H:%M:%S %Z")
        raise ValidationError(
            f"The latest physical event ({latest.operation}) was at {latest_time}. "
            "Choose an action time after that event, or refresh to use the current time."
        )
    if not slot.box.puck_id:
        if not puck_id:
            raise ValidationError("Choose the puck for this box before placing the grid.")
        change_box(
            actor=actor,
            box_id=slot.box_id,
            expected_version=slot.box.version,
            action="move",
            puck_id=puck_id,
            occurred_at=occurred_at,
        )
        # Moving the box may also update this grid if it already occupied the box.
        grid.refresh_from_db()
    before = location(grid)
    if clipped and not grid.is_clipped:
        GridEvent.objects.create(
            grid=grid, actor=actor, operation="clipped", occurred_at=occurred_at
        )
    if current:
        current.grid = None
        current.save(update_fields=["grid"])
    slot.grid = grid
    slot.save(update_fields=["grid"])
    grid.is_clipped = clipped
    grid.version += 1
    grid.save(update_fields=["is_clipped", "version", "updated_at"])
    GridEvent.objects.create(
        grid=grid,
        actor=actor,
        operation="moved" if current else "stored",
        occurred_at=occurred_at,
        from_slot=current,
        to_slot=slot,
        details={"from": before, "to": location(grid)},
    )
    sync_puck_locations(actor=actor)
    return grid


@transaction.atomic
def save_preparation_and_clipping(*, actor, grid_id, preparation, clipped, expected_version):
    from .services import record_audit, update_grid_preparation

    lock_inventory()
    grid = Grid.objects.select_for_update().get(pk=grid_id)
    require_grid_editor(actor, grid)
    if type(clipped) is not bool:
        raise ValidationError("Choose the clipping state.")
    current = GridSlot.objects.select_related("box__box_type").filter(grid=grid).first()
    changed = clipped != grid.is_clipped
    if changed and current and current.box.transferred_at:
        raise ValidationError(
            "This grid has left CCI. Correct a mistaken transfer before editing clipping."
        )
    grid = update_grid_preparation(
        actor=actor, grid_id=grid_id, preparation=preparation, expected_version=expected_version
    )
    if not changed:
        return grid, False
    before = location(grid)
    old = grid.is_clipped
    released = False
    if current:
        spec = current.box.box_type.layout.get(current.side)
        if not spec or spec["clipped"] != clipped:
            current.grid = None
            current.save(update_fields=["grid"])
            released = True
    grid.is_clipped = clipped
    grid.version += 1
    grid.save(update_fields=["is_clipped", "version", "updated_at"])
    GridEvent.objects.create(
        grid=grid,
        actor=actor,
        operation="clipping_updated",
        occurred_at=timezone.now(),
        from_slot=current,
        to_slot=None if released else current,
        details={
            "before_clipped": old,
            "after_clipped": clipped,
            "from": before,
            "to": location(grid),
            "location_needs_review": released,
        },
    )
    record_audit(
        actor,
        grid,
        "update_clipping",
        {"is_clipped": {"before": old, "after": clipped}, "location_released": released},
    )
    sync_puck_locations(actor=actor)
    return grid, released
