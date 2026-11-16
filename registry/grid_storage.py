"""Physical placement commands share the inventory lock with box actions."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .models import Grid
from .permissions import require_grid_editor
from .storage import change_box, lock_inventory, sync_puck_locations
from .storage_models import GridEvent, GridSlot


def slot_label(slot):
    if len(slot.box.box_type.layout) > 1:
        return ("C" if slot.side == "clipped" else "U") + str(slot.position)
    return str(slot.position)


def discard_location(grid):
    """Use the recorded discard event, which survives later reuse of its box."""
    if grid.status not in (Grid.Status.DISCARDED, Grid.Status.SCREENED_DISCARDED):
        return None
    events = grid.physical_events.all()
    event = max(
        (event for event in events if event.operation == "discarded"),
        key=lambda event: event.pk,
        default=None,
    )
    if not event:
        return "Discarded — location unknown"
    site = event.details.get("discard_location")
    if not site and event.from_slot_id:
        site = "CCI"  # Earlier discard actions were permitted only for CCI boxes.
    return f"Discarded at {site}" if site else "Discarded — location unknown"


def location(grid):
    discarded = discard_location(grid)
    if discarded:
        return discarded
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
    if grid.status in (Grid.Status.DISCARDED, Grid.Status.SCREENED_DISCARDED):
        raise ValidationError("A discarded grid cannot be stored.")
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
    if grid.status == Grid.Status.UNKNOWN:
        grid.status = Grid.Status.IN_STORAGE
    grid.version += 1
    grid.save(update_fields=["is_clipped", "status", "version", "updated_at"])
    GridEvent.objects.create(
        grid=grid,
        actor=actor,
        operation="moved" if current else "stored",
        occurred_at=occurred_at,
        from_slot=current,
        to_slot=slot,
        details={"from": before, "to": location(grid)},
    )
    sync_puck_locations(actor=actor, emptied_puck_ids=[current.box.puck_id] if current else [])
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
    if changed and grid.status in (Grid.Status.DISCARDED, Grid.Status.SCREENED_DISCARDED):
        raise ValidationError("A discarded grid cannot change clipping state.")
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
    if released and grid.status == Grid.Status.IN_STORAGE:
        grid.status = Grid.Status.UNKNOWN
    grid.version += 1
    grid.save(update_fields=["is_clipped", "status", "version", "updated_at"])
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
    sync_puck_locations(actor=actor, emptied_puck_ids=[current.box.puck_id] if released else [])
    return grid, released


@transaction.atomic
def record_grid_outcome(*, actor, grid_id, outcome, reason, expected_version):
    """Record a completed screening or discard as physical history."""
    lock_inventory()
    grid = Grid.objects.select_for_update().get(pk=grid_id)
    actor = require_grid_editor(actor, grid)
    if type(expected_version) is not int or grid.version != expected_version:
        raise ValidationError("This grid changed. Reload before recording the outcome.")
    if grid.status in (Grid.Status.DISCARDED, Grid.Status.SCREENED_DISCARDED):
        raise ValidationError("This grid has already been discarded.")
    slot = GridSlot.objects.select_related("box__puck", "box__box_type").filter(grid=grid).first()
    if slot and slot.box.transferred_at:
        raise ValidationError("This grid has left CCI with its box.")
    allowed = {
        Grid.Status.SCREENED_RECOVERED,
        Grid.Status.SCREENED_DISCARDED,
        Grid.Status.DISCARDED,
    }
    if outcome not in allowed:
        raise ValidationError("Choose a valid grid outcome.")
    if outcome in (Grid.Status.SCREENED_RECOVERED, Grid.Status.SCREENED_DISCARDED) and not slot:
        raise ValidationError("Record the grid's box and slot before screening.")
    now = timezone.now()
    latest = grid.physical_events.order_by("-occurred_at").first()
    if latest and now < latest.occurred_at:
        raise ValidationError("The latest physical event is in the future. Review its time first.")
    already_screened = grid.status == Grid.Status.SCREENED_RECOVERED
    if outcome == Grid.Status.DISCARDED and already_screened:
        outcome = Grid.Status.SCREENED_DISCARDED
    if reason.strip() and outcome == Grid.Status.SCREENED_RECOVERED:
        raise ValidationError("A discard reason can only be entered when discarding the grid.")
    if (
        outcome in (Grid.Status.SCREENED_RECOVERED, Grid.Status.SCREENED_DISCARDED)
        and not already_screened
    ):
        GridEvent.objects.create(
            grid=grid,
            actor=actor,
            operation="screened",
            occurred_at=now,
            from_slot=slot,
            to_slot=slot,
            details={"previous_status": grid.status},
        )
    if outcome != Grid.Status.SCREENED_RECOVERED:
        GridEvent.objects.create(
            grid=grid,
            actor=actor,
            operation="discarded",
            occurred_at=now,
            from_slot=slot,
            details={
                "reason": reason.strip(),
                "discard_location": "CCI",
                "previous_status": grid.status,
            },
        )
        if slot:
            slot.grid = None
            slot.save(update_fields=["grid"])
    grid.status = outcome
    grid.version += 1
    grid.save(update_fields=["status", "version", "updated_at"])
    if slot and outcome != Grid.Status.SCREENED_RECOVERED:
        sync_puck_locations(actor=actor, emptied_puck_ids=[slot.box.puck_id])
    return grid


@sensitive_variables("approval")
@transaction.atomic
def correct_grid_outcome(*, actor, grid_id, expected_version, event_id, approval, reason):
    from .services import record_audit

    lock_inventory()
    grid = Grid.objects.select_for_update().get(pk=grid_id)
    actor = require_grid_editor(actor, grid)
    if not isinstance(approval, str) or approval.strip() != "approve":
        raise ValidationError("Type approve to confirm.")
    reason = reason.strip()
    if not reason:
        raise ValidationError("Enter a reason for this correction.")
    latest = grid.physical_events.order_by("-pk").first()
    if grid.version != expected_version or not latest or latest.pk != event_id:
        raise ValidationError("This grid changed. Reload before correcting its status.")
    if latest.operation not in {"screened", "discarded"}:
        raise ValidationError("Only the latest screening or discard action can be corrected.")
    if grid.status not in {
        Grid.Status.SCREENED_RECOVERED,
        Grid.Status.DISCARDED,
        Grid.Status.SCREENED_DISCARDED,
    }:
        raise ValidationError("This status cannot be corrected here.")
    slot = None
    if latest.from_slot_id:
        slot = (
            GridSlot.objects.select_for_update(of=("self",))
            .select_related("box__box_type", "box__puck")
            .get(pk=latest.from_slot_id)
        )
        if slot.box.events.filter(recorded_at__gt=latest.recorded_at).exists():
            raise ValidationError(
                "The gridbox changed after this action. Review its history first."
            )
        if slot.box.discarded or slot.box.transferred_at or not slot.box.puck_id:
            raise ValidationError(
                "The original gridbox must be in a CCI puck before restoring the grid."
            )
        spec = slot.box.box_type.layout.get(slot.side)
        if not spec or spec.get("clipped") != grid.is_clipped:
            raise ValidationError("The original slot is no longer compatible with this grid.")
        if slot.grid_id not in (None, grid.pk):
            raise ValidationError(
                "The original slot is occupied. Resolve the slot before correcting this status."
            )
    previous = latest.details.get("previous_status")
    if previous is None:
        earlier_screening = grid.physical_events.filter(
            operation="screened", occurred_at__lt=latest.occurred_at
        ).exists()
        previous = (
            Grid.Status.SCREENED_RECOVERED
            if earlier_screening
            else (Grid.Status.IN_STORAGE if slot else Grid.Status.UNKNOWN)
        )
    if previous not in {
        Grid.Status.UNKNOWN,
        Grid.Status.IN_STORAGE,
        Grid.Status.SCREENED_RECOVERED,
    }:
        raise ValidationError("The previous status cannot be restored automatically.")
    if slot and slot.grid_id is None:
        slot.grid = grid
        slot.save(update_fields=["grid"])
    old_status = grid.status
    grid.status = previous
    grid.version += 1
    grid.save(update_fields=["status", "version", "updated_at"])
    GridEvent.objects.create(
        grid=grid,
        actor=actor,
        operation="status_correction",
        occurred_at=timezone.now(),
        to_slot=slot,
        details={
            "corrected_event_id": latest.pk,
            "reason": reason,
            "before_status": old_status,
            "after_status": previous,
        },
    )
    record_audit(
        actor,
        grid,
        "correct_status",
        {
            "event_id": latest.pk,
            "reason": reason,
            "before_status": old_status,
            "after_status": previous,
        },
    )
    sync_puck_locations(actor=actor)
    return grid
