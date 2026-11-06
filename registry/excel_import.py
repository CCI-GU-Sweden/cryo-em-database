"""Preview and apply current-format workbooks without overwriting records.

Both paths build the same plan. Confirmation rebuilds it inside a transaction,
so a preview is never permission to overwrite a record changed in the meantime.
"""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from uuid import UUID, uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import User

from .models import AuditEvent, Grid, PreparationSession, SampleOwner
from .permissions import require_grid_importer
from .preparation import PREPARATION_FIELDS, preparation_snapshot
from .services import record_audit, remember_preparation_values, validate_preparation


@dataclass
class ImportPlan:
    owners: dict
    sessions: dict
    grids: list
    report: dict


def _text(row, key):
    value = row.get(key)
    return "" if value is None else str(value)


def _unique_rows(rows, key, title):
    result = {}
    for row in rows:
        identifier = _text(row, key).strip()
        if not identifier or identifier.casefold() in result:
            raise ValidationError(f"{title} row {row['_row']}: missing or duplicate {key}.")
        result[identifier.casefold()] = row
    return result


def _session_values(row, snapshot, owner, warnings):
    timestamp = _text(row, "prepared_at").strip()
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", timestamp):
            # A supplied date with no time explicitly defaults to facility-local
            # noon. The timezone supplies the offset for that date, including DST.
            facility_timezone = timezone.get_default_timezone()
            prepared_at = timezone.make_aware(
                datetime.combine(date.fromisoformat(timestamp), time(12)), facility_timezone
            )
            warnings.add(
                f"Preparation date {timestamp}: time defaults to 12:00 {facility_timezone}."
            )
        else:
            prepared_at = parse_datetime(timestamp) if timestamp else None
    except ValueError as error:
        raise ValidationError(
            "Enter a valid YYYY-MM-DD date or timestamp with a UTC offset."
        ) from error
    if timestamp and (prepared_at is None or timezone.is_naive(prepared_at)):
        raise ValidationError("Use YYYY-MM-DD, or include a UTC offset when supplying a time.")
    operator = _text(row, "prepared_by")
    user = User.objects.filter(username=operator).first() if operator else None
    if operator and user is None:
        warnings.add(
            f"Operator '{operator}' has no local account; preparation operator stays unknown."
        )
    try:
        defaults = json.loads(_text(snapshot, "defaults"))
        version = int(_text(snapshot, "defaults_schema_version"))
    except (ValueError, TypeError) as error:
        raise ValidationError(
            "Session defaults must be a JSON object with a whole-number version."
        ) from error
    if not isinstance(defaults, dict) or version < 1:
        raise ValidationError("Session defaults must be a JSON object with a positive version.")
    # Validate current scientific defaults without replacing the original snapshot.
    if version in (4, 5, 6, 7) and defaults:
        # Older snapshots remain immutable and may contain the retired field.
        current_defaults = dict(defaults)
        if version == 4:
            current_defaults.pop("grid_type_reference", None)
        if version < 6:
            # Historical free text and nm values remain in the immutable snapshot.
            current_defaults.pop("carbon_description", None)
        validate_preparation(current_defaults)
    return {
        "owner": owner,
        "prepared_by": user,
        "prepared_at": prepared_at,
        "experiment_reference": _text(row, "experiment_reference"),
        "project_reference": _text(row, "project_reference"),
        "notes": _text(row, "session_notes"),
        "defaults": defaults,
        "defaults_schema_version": version,
    }


def _same_session(session, values):
    return all(getattr(session, name) == value for name, value in values.items())


def _session_source(label, snapshot, rows):
    """Resolve explicit file labels without grouping by guessed dates or owners.

    Exports carry a portable key. Hand-made files do not: existing grid IDs can
    identify a previous import of this explicitly labelled group; otherwise it
    creates a new session. A label alone never identifies a database session.
    """
    if snapshot:
        key = str(UUID(_text(snapshot, "session_key")))
        return key, snapshot
    identifiers = [
        _text(row, "grid_number")
        for row in rows
        if _text(row, "session_key").strip().casefold() == label
        and any(row.get(name) not in (None, "") for name in PREPARATION_FIELDS)
    ]
    matches = list(PreparationSession.objects.filter(grids__grid_number__in=identifiers).distinct())
    if len(matches) > 1:
        raise ValidationError("This Session label combines grids from different existing sessions.")
    existing = matches[0] if matches else None
    return (
        str(existing.request_token) if existing else str(uuid4()),
        {
            "defaults_schema_version": existing.defaults_schema_version if existing else 7,
            "defaults": json.dumps(existing.defaults if existing else {}),
        },
    )


def _preparation_values(row):
    # Excel blanks become empty text or unknown measurements, according to the
    # model. Do not replace blank numeric measurements with zero.
    values = {}
    for name in PREPARATION_FIELDS:
        value = row.get(name)
        if isinstance(value, bool):
            raise ValidationError(f"{name}: enter a value, not TRUE or FALSE.")
        if value is None and Grid._meta.get_field(name).empty_strings_allowed:
            value = ""
        values[name] = value
    return validate_preparation(values)


def _build_plan(payload):
    owner_rows = _unique_rows(payload["owners"], "code", "Owners")
    snapshots = _unique_rows(payload["sessions"], "session_label", "Sessions")
    _unique_rows(payload["sessions"], "session_key", "Sessions")
    owners, sessions, grids = {}, {}, []
    warnings, identifiers, errors = set(), set(), []
    report = {
        "new_grids": 0,
        "existing_grids": 0,
        "skipped_rows": 0,
        "new_sessions": 0,
        "new_owners": [],
        "warnings": [],
    }

    for row in payload["grids"]:
        number = row["_row"]
        try:
            # Blank preallocated identifiers are not physical grids. Explicit
            # zero measurements/counts do count as entered scientific values.
            if not any(row.get(name) not in (None, "") for name in PREPARATION_FIELDS):
                report["skipped_rows"] += 1
                continue
            identifier = _text(row, "grid_number")
            if not identifier or identifier != identifier.strip():
                raise ValidationError("A grid ID is required and cannot have surrounding spaces.")
            if identifier.casefold() in identifiers:
                raise ValidationError(f"Duplicate grid ID: {identifier}.")
            identifiers.add(identifier.casefold())
            code = _text(row, "owner_code").casefold()
            if code not in owner_rows:
                raise ValidationError("Owner is missing from the Owners worksheet.")
            if code not in owners:
                source = owner_rows[code]
                active = source.get("active")
                if active not in (True, False) or type(active) is not bool:
                    raise ValidationError("Owner Active must be TRUE or FALSE.")
                values = {
                    name: _text(source, name) for name in ("code", "name", "affiliation", "notes")
                }
                values["active"] = active
                owner = SampleOwner.objects.filter(code__iexact=code).first()
                if owner:
                    if any(getattr(owner, name) != value for name, value in values.items()):
                        raise ValidationError(
                            f"Owner conflict for {source['code']}; existing details differ."
                        )
                else:
                    owner = SampleOwner(**values)
                    owner.full_clean()
                    report["new_owners"].append({"name": owner.name, "code": owner.code})
                owners[code] = owner
            owner = owners[code]
            if _text(row, "owner_name") != owner.name:
                raise ValidationError("Sample owner name differs from the Owners worksheet.")
            label = _text(row, "session_key").strip().casefold()
            if not label or len(label) > 100:
                raise ValidationError(
                    "Enter a Session label, for example session-1 (up to 100 characters)."
                )
            snapshot = snapshots.get(label)
            if label not in sessions:
                key, source = _session_source(label, snapshot, payload["grids"])
            else:
                existing = sessions[label]
                key = str(existing.request_token)
                source = snapshot or {
                    "defaults_schema_version": existing.defaults_schema_version,
                    "defaults": json.dumps(existing.defaults),
                }
            if snapshot is None:
                warnings.add(
                    f"Session '{label}': no original-defaults metadata supplied; "
                    "existing defaults are preserved or left unknown for new sessions."
                )
            values = _session_values(row, source, owner, warnings)
            if label not in sessions:
                session = PreparationSession.objects.filter(request_token=key).first()
                if session:
                    if not _same_session(session, values):
                        raise ValidationError(
                            "Session conflict: existing metadata or defaults differ."
                        )
                else:
                    session = PreparationSession(request_token=key, **values)
                    # New owners are saved first on confirmation. Validate other
                    # fields now, without pretending the owner already has a PK.
                    # An empty defaults object explicitly means unknown for hand
                    # entry. Its JSON shape was validated above; ModelForm-style
                    # blank checks must not turn it into an invented snapshot.
                    session.full_clean(exclude=["owner", "prepared_by", "prepared_at", "defaults"])
                    report["new_sessions"] += 1
                sessions[label] = session
            session = sessions[label]
            if not _same_session(session, values):
                raise ValidationError(
                    "Rows with one Session label must have identical session details."
                )
            preparation = _preparation_values(row)
            grid = Grid.objects.filter(grid_number__iexact=identifier).first()
            if grid:
                if hasattr(grid, "deletion"):
                    raise ValidationError(
                        f"Grid {identifier} is archived; its ID remains reserved."
                    )
                same = (
                    grid.grid_number == identifier
                    and grid.session.request_token == session.request_token
                    and all(getattr(grid, name) == value for name, value in preparation.items())
                )
                if not same:
                    raise ValidationError(f"Grid conflict for {identifier}; existing data differs.")
                report["existing_grids"] += 1
            else:
                grid = Grid(grid_number=identifier, session=session, **preparation)
                grid.full_clean(exclude=["session"])
                report["new_grids"] += 1
            grids.append({"grid": grid, "session": session, "source": row})
        except (ValidationError, ValueError) as error:
            details = (
                error.messages if isinstance(error, ValidationError) else ["Invalid session key."]
            )
            errors.extend(f"Grids row {number}: {message}" for message in details)
    if errors:
        raise ValidationError(errors[:50])
    report["warnings"] = sorted(warnings)
    return ImportPlan(owners, sessions, grids, report)


def preview_import(*, actor, payload):
    require_grid_importer(actor)
    return _build_plan(payload).report


@transaction.atomic
def _apply_import(actor, payload):
    # Match owner-registration locking, then lock existing owners in stable order.
    # This serializes imports with normal per-owner grid ID allocation.
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE registry_sampleowner IN SHARE ROW EXCLUSIVE MODE")
    codes = [_text(row, "code") for row in payload["owners"]]
    list(SampleOwner.objects.select_for_update().filter(code__in=codes).order_by("pk"))
    plan = _build_plan(payload)
    if not plan.report["new_grids"]:
        return plan.report
    for owner in plan.owners.values():
        if not owner.pk:
            owner.save()
            record_audit(
                actor,
                owner,
                "import",
                {
                    name: {"before": None, "after": getattr(owner, name)}
                    for name in ("code", "name", "affiliation", "notes", "active")
                },
                source="excel",
            )
    for session in plan.sessions.values():
        if not session.pk:
            # Refresh the cached FK now that any new owner has been saved.
            session.owner_id = session.owner.pk
            session.full_clean(exclude=["prepared_by", "prepared_at", "defaults"])
            session.save()
            record_audit(
                actor,
                session,
                "import",
                {
                    "defaults": {"before": None, "after": session.defaults},
                    "source_sha256": payload["sha256"],
                },
                source="excel",
            )
    for entry in plan.grids:
        grid = entry["grid"]
        if grid.pk:
            continue
        grid.session = entry["session"]
        grid.save()
        remember_preparation_values(grid)
        record_audit(
            actor,
            grid,
            "import",
            {
                "preparation": {"before": None, "after": preparation_snapshot(grid)},
                "source": {
                    "filename": payload["filename"],
                    "sha256": payload["sha256"],
                    "sheet": "Grids",
                    "row": entry["source"],
                },
            },
            source="excel",
        )
    AuditEvent.objects.create(
        actor=actor,
        entity_type="ExcelImport",
        entity_id=payload["sha256"],
        operation="import",
        source="excel",
        changes=plan.report,
    )
    return plan.report


def import_workbook(*, actor, payload):
    actor = require_grid_importer(actor)
    try:
        return _apply_import(actor, payload)
    except IntegrityError as error:
        raise ValidationError(
            "An import conflict occurred. Preview again; no records were imported."
        ) from error
