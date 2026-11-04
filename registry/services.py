"""Small, explicit commands: authorization, validation and audit share a transaction."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .identifiers import MAX_GRID_SEQUENCE, grid_suffix, suffix_sequence
from .models import (
    AuditEvent,
    DeletedGrid,
    Grid,
    GridIdentifierCounter,
    OwnerAccessGrant,
    PreparationSession,
    PreparationSuggestion,
    SampleOwner,
)
from .permissions import current_staff, require_grid_editor, require_session_registration
from .preparation import PREPARATION_FIELDS, compact_decimal, preparation_snapshot


def record_audit(actor, instance, operation, changes, source="ui"):
    AuditEvent.objects.create(
        actor=actor,
        entity_type=type(instance).__name__,
        entity_id=str(instance.pk),
        operation=operation,
        changes=changes,
        source=source,
    )


def owner_code_candidates(name: str):
    """Readable four-character codes, with progressively more room for numbers.

    First/last words supply the name parts. Strip accents for portable codes;
    short or non-Latin names use x padding. A single word supplies its first four
    letters. Existing owner codes are never changed by this convention.
    """
    words = name.split()

    def letters(word):
        normalized = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode()
        return "".join(character for character in normalized.lower() if "a" <= character <= "z")

    if len(words) >= 2:
        first = letters(words[0])[:2].ljust(2, "x")
        last = letters(words[-1])[:2].ljust(2, "x")
    else:
        base = letters(words[0] if words else "")[:4].ljust(4, "x")
        first, last = base[:2], base[2:]
    yield first + last
    for number in range(1, 10):
        yield first[0] + last + str(number)
    for number in range(10, 100):
        yield first[0] + last[0] + str(number)
    for number in range(100, 1000):
        yield first[0] + str(number)


def suggest_owner_code(name: str) -> str:
    """Check every candidate against all owners, including inactive records."""
    for candidate in owner_code_candidates(name):
        if not SampleOwner.objects.filter(code__iexact=candidate).exists():
            return candidate
    raise ValidationError(
        "All four-character codes for this name are in use. Contact an administrator."
    )


def validate_preparation(values):
    unexpected = set(values) - set(PREPARATION_FIELDS)
    if unexpected:
        raise ValidationError("Only preparation fields may be changed.")
    values = dict(values)
    count = values.get("multiple_blot")
    if count is None or count == "":
        count = 0
        values["multiple_blot"] = 0
    # Reject fractions before IntegerField can coerce them (1.5 must not become 1).
    try:
        numeric = Decimal(str(count))
        valid = type(count) is not bool and numeric.is_finite() and numeric >= 0
        valid = valid and numeric == numeric.to_integral_value()
    except (InvalidOperation, ValueError):
        valid = False
    if not valid:
        raise ValidationError({"multiple_blot": "Enter a whole number, 0 or greater."})
    grid = Grid(**values)
    grid.full_clean(exclude=["grid_number", "session"])
    if grid.sample_concentration_value is not None and not grid.sample_concentration_unit.strip():
        raise ValidationError({"sample_concentration_unit": "Enter a unit for the concentration."})
    return {name: getattr(grid, name) for name in PREPARATION_FIELDS}


def remember_preparation_values(grid):
    """Keep reusable values even when the last grid using one is later edited."""
    for name in PREPARATION_FIELDS:
        value = getattr(grid, name)
        if value is None or value == "" or isinstance(value, bool):
            continue
        text = str(compact_decimal(value))
        if len(text) <= 500:
            PreparationSuggestion.objects.get_or_create(
                field_name=name, value=text, defaults={"source": {"type": "staff_entry"}}
            )


@transaction.atomic
def create_preparation_session(
    *,
    actor,
    owner,
    prepared_at,
    grid_count,
    preparation,
    request_token,
    experiment_reference="",
    project_reference="",
    notes="",
):
    actor = require_session_registration(actor, owner)
    if not settings.GRID_REGISTRATION_ENABLED:
        raise ValidationError("Grid registration is currently disabled.")
    if type(grid_count) is not int or not 1 <= grid_count <= 100:
        raise ValidationError("Choose between 1 and 100 grids for this prototype session.")
    if prepared_at is None or timezone.is_naive(prepared_at):
        raise ValidationError("Enter the preparation date and time with a timezone.")
    try:
        request_token = UUID(str(request_token))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError("The submission token is invalid. Reload the form.") from error
    values = validate_preparation(preparation)
    defaults = preparation_snapshot(Grid(**values))

    # Lock the owner before the first counter is created. This serializes batches
    # for the same owner while different owners keep independent sequences.
    owner = SampleOwner.objects.select_for_update().get(pk=owner.pk)
    if not owner.active:
        raise PermissionDenied("Choose an active sample owner.")
    existing = PreparationSession.objects.filter(request_token=request_token).first()
    if existing:
        same_request = (
            existing.owner_id == owner.pk
            and existing.prepared_by_id == actor.pk
            and existing.prepared_at == prepared_at
            and existing.defaults == defaults
            and existing.experiment_reference == experiment_reference
            and existing.project_reference == project_reference
            and existing.notes == notes
            and existing.grids.count() == grid_count
        )
        if not same_request:
            raise ValidationError("This submission was already used. Start a new session form.")
        return existing

    if not re.fullmatch(r"[a-z0-9]{4}", owner.code):
        raise ValidationError(
            "This owner needs a four-character lowercase code before generating grids."
        )
    counter, _ = GridIdentifierCounter.objects.get_or_create(namespace=f"owner:{owner.pk}")
    # Honor IDs already present (for example from a future historical import),
    # not just the counter. Unrecognized legacy formats are preserved as-is.
    highest_existing = 0
    for identifier in Grid.objects.filter(grid_number__istartswith=f"{owner.code}-").values_list(
        "grid_number", flat=True
    ):
        sequence = suffix_sequence(identifier[len(owner.code) + 1 :])
        if sequence is not None:
            highest_existing = max(highest_existing, sequence)
    counter.next_number = max(counter.next_number, highest_existing + 1)
    if counter.next_number + grid_count - 1 > MAX_GRID_SEQUENCE:
        raise ValidationError("Not enough grid IDs remain for this owner. The last suffix is z999.")

    session = PreparationSession(
        owner=owner,
        prepared_by=actor,
        prepared_at=prepared_at,
        defaults=defaults,
        request_token=request_token,
        experiment_reference=experiment_reference,
        project_reference=project_reference,
        notes=notes,
    )
    session.full_clean()
    try:
        # Different owners have independent locks. A reused submission token can
        # therefore race across owners; translate that unique conflict safely.
        with transaction.atomic():
            session.save()
    except IntegrityError as error:
        if PreparationSession.objects.filter(request_token=request_token).exists():
            raise ValidationError(
                "This submission was already used. Start a new session form."
            ) from error
        raise
    record_audit(
        actor,
        session,
        "create",
        {
            "owner_id": {"before": None, "after": owner.pk},
            "prepared_by_id": {"before": None, "after": actor.pk},
            "prepared_at": {"before": None, "after": prepared_at.isoformat()},
            "experiment_reference": {"before": None, "after": experiment_reference},
            "project_reference": {"before": None, "after": project_reference},
            "notes": {"before": None, "after": notes},
            "defaults": {"before": None, "after": defaults},
        },
    )
    for number in range(counter.next_number, counter.next_number + grid_count):
        grid = Grid(session=session, grid_number=f"{owner.code}-{grid_suffix(number)}", **values)
        grid.full_clean()
        grid.save()
        record_audit(
            actor,
            grid,
            "create",
            {
                "grid_number": {"before": None, "after": grid.grid_number},
                "preparation": {"before": None, "after": defaults},
            },
        )
    counter.next_number += grid_count
    remember_preparation_values(Grid(**values))
    counter.save(update_fields=["next_number"])
    return session


@transaction.atomic
def update_grid_preparation(*, actor, grid_id, preparation, expected_version):
    grid = Grid.objects.select_for_update().select_related("session__owner").get(pk=grid_id)
    actor = require_grid_editor(actor, grid)
    if grid.version != expected_version:
        raise ValidationError("This grid changed since you opened it. Reload before editing again.")
    # A direct service caller may send only the changed fields. Preserve the
    # remaining values instead of turning omitted measurements into unknowns.
    existing_values = {name: getattr(grid, name) for name in PREPARATION_FIELDS}
    values = validate_preparation({**existing_values, **preparation})
    before = preparation_snapshot(grid)
    changed_fields = [name for name in PREPARATION_FIELDS if getattr(grid, name) != values[name]]
    if not changed_fields:
        return grid

    remember_preparation_values(grid)
    for name in changed_fields:
        setattr(grid, name, values[name])
    grid.version += 1
    grid.full_clean()
    grid.save(update_fields=[*changed_fields, "version", "updated_at"])
    after = preparation_snapshot(grid)
    record_audit(
        actor,
        grid,
        "update",
        {name: {"before": before[name], "after": after[name]} for name in changed_fields},
    )
    remember_preparation_values(grid)
    return grid


def allocate_owner_code(name, preferred_code):
    """Call inside a transaction so the checked code stays unique until saved."""
    # Registrations are infrequent; a short lock keeps this allocation readable
    # and safe even when two people save the same suggestion simultaneously.
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE registry_sampleowner IN SHARE ROW EXCLUSIVE MODE")
    if (
        preferred_code in owner_code_candidates(name)
        and not SampleOwner.objects.filter(code__iexact=preferred_code).exists()
    ):
        return preferred_code
    return suggest_owner_code(name)


@transaction.atomic
def create_sample_owner(*, actor, name, affiliation="", notes="", preferred_code=""):
    """Staff register an owner; all active CCI staff already have editing access.

    This command deliberately cannot update an existing owner or assign rights
    to another user. Those administration operations retain their own boundary.
    """
    actor = current_staff(actor)
    owner = SampleOwner(name=name, affiliation=affiliation, notes=notes)
    owner.code = allocate_owner_code(name, preferred_code)
    owner.full_clean()
    owner.save()
    record_audit(
        actor,
        owner,
        "create",
        {
            field: {"before": None, "after": getattr(owner, field)}
            for field in ("name", "code", "affiliation", "notes", "active")
        },
    )
    return owner


@transaction.atomic
def save_administration_record(*, actor, instance, preferred_code=""):
    """Admin forms validate input first; this boundary enforces access and auditing."""
    actor = current_staff(actor)
    if not actor.is_superuser:
        raise PermissionDenied("Only a facility administrator can manage owners and grants.")
    if not isinstance(instance, (SampleOwner, OwnerAccessGrant)):
        raise ValidationError("Unsupported administration record.")
    names = [
        field.attname
        for field in instance._meta.fields
        if field.name not in {"id", "created_at", "updated_at"}
    ]
    before = {}
    if instance.pk:
        previous = type(instance).objects.select_for_update().get(pk=instance.pk)
        before = {name: getattr(previous, name) for name in names}
        if isinstance(instance, SampleOwner):
            # A spelling correction must not change the owner's assigned code.
            instance.code = previous.code
    elif isinstance(instance, SampleOwner):
        instance.code = allocate_owner_code(instance.name, preferred_code)
    instance.full_clean()
    instance.save()
    changes = {
        name: {"before": before.get(name), "after": getattr(instance, name)}
        for name in names
        if before.get(name) != getattr(instance, name)
    }
    if changes:
        record_audit(actor, instance, "update" if before else "create", changes, source="admin")
    return instance


@sensitive_variables("password")
@transaction.atomic
def archive_grid(*, actor, grid_id, password, expected_version):
    """Reauthenticate the acting staff member before moving one record to archive.

    This corrects a database registration mistake; it is not a physical discard
    event. Lock the grid to serialize deletion with edits and repeat submissions.
    """
    actor = current_staff(actor)
    if not actor.has_usable_password():
        raise ValidationError(
            {"password": "This account has no local password. Contact an administrator."}
        )
    if not isinstance(password, str) or not actor.check_password(password):
        raise ValidationError({"password": "Your password is incorrect. The grid was not deleted."})
    grid = Grid.objects.select_for_update().get(pk=grid_id)
    existing = DeletedGrid.objects.filter(grid=grid).first()
    if existing:
        return existing  # A retried confirmation never creates duplicate history.
    if type(expected_version) is not int or grid.version != expected_version:
        raise ValidationError("This grid changed since you opened it. Reload before deleting it.")
    # Update before adding the marker: the database freezes archived grid rows.
    grid.version += 1
    grid.save(update_fields=["version", "updated_at"])
    deleted = DeletedGrid.objects.create(grid=grid, deleted_by=actor)
    record_audit(
        actor,
        grid,
        "archive",
        {
            "deleted": {"before": False, "after": True},
            "deleted_by_id": {"before": None, "after": actor.pk},
            "deleted_at": {"before": None, "after": deleted.deleted_at.isoformat()},
        },
    )
    return deleted
