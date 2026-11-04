"""The current Excel format: explicit columns, portable keys and literal text.

Grids is the familiar flat worksheet. Owners supplies owner profiles; Sessions
preserves the original defaults separately from each grid's actual conditions.
This module only reads/writes files; database changes live in excel_import.py.
"""

import hashlib
import json
from datetime import datetime, time
from decimal import Decimal
from io import BytesIO
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError
from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font, PatternFill
from openpyxl.styles.numbers import is_datetime
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from .forms import PreparationForm
from .permissions import current_staff
from .preparation import PREPARATION_FIELDS, PREPARATION_GROUPS

FORMAT_MARKER = "CCI Grid Registry workbook v1"
MAX_ROWS = 5000
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_UNPACKED_BYTES = 50 * 1024 * 1024

_CONTEXT_COLUMNS = [
    ("grid_number", "Grid ID"),
    ("owner_name", "Sample owner"),
    ("owner_code", "Owner code"),
    ("session_key", "Session"),
    ("prepared_by", "Operator login"),
    ("prepared_at", "Preparation date and time"),
    ("experiment_reference", "Experiment reference"),
    ("project_reference", "Project reference"),
    ("session_notes", "Session notes"),
]
_preparation_form = PreparationForm()
_labels = dict(_CONTEXT_COLUMNS)
_labels.update({name: _preparation_form[name].label for name in PREPARATION_FIELDS})
_labels["notes"] = "Grid notes"
GRID_GROUPS = [
    (
        "Info",
        [
            "grid_number",
            "owner_name",
            "owner_code",
            "session_key",
            "prepared_by",
            "prepared_at",
        ],
    ),
    ("Sample conditions", PREPARATION_GROUPS[0][1]),
    ("Grid treatment", PREPARATION_GROUPS[1][1] + PREPARATION_GROUPS[2][1]),
    ("Freezing conditions", PREPARATION_GROUPS[3][1]),
    ("Experiment reference", ["experiment_reference", "project_reference"]),
    ("Additional notes", ["notes", "session_notes"]),
]
GRID_COLUMNS = [(name, _labels[name]) for _, names in GRID_GROUPS for name in names]
# A short repeating palette keeps related columns together without assigning
# scientific meaning to a colour. Dark headings contrast with pale data cells.
GROUP_COLORS = [
    ("245567", "EAF4F3"),  # Teal
    ("584B78", "F1ECF7"),  # Purple
    ("72551F", "FFF5DF"),  # Amber
]
OWNER_COLUMNS = [
    ("code", "Owner code"),
    ("name", "Sample owner"),
    ("affiliation", "Affiliation"),
    ("notes", "Owner notes"),
    ("active", "Active"),
]
SESSION_COLUMNS = [
    ("session_label", "Session"),
    ("session_key", "Session key"),
    ("defaults_schema_version", "Defaults version"),
    ("defaults", "Original session defaults (JSON)"),
]
SHEETS = {"Grids": GRID_COLUMNS, "Owners": OWNER_COLUMNS, "Sessions": SESSION_COLUMNS}


def _write_sheet(book, title, columns, rows):
    sheet = book.create_sheet(title)
    header_row = 2 if title == "Grids" else 1
    if title == "Grids":
        start = 1
        for group, names in GRID_GROUPS:
            finish = start + len(names) - 1
            sheet.merge_cells(start_row=1, start_column=start, end_row=1, end_column=finish)
            sheet.cell(1, start, group)
            start = finish + 1
    sheet.append([label for _, label in columns])
    for number, row in enumerate(rows, header_row + 1):
        for column, (key, _) in enumerate(columns, 1):
            value = row.get(key)
            if isinstance(value, Decimal):
                cell = sheet.cell(number, column, value)
                cell.number_format = "0.00"
                continue
            # Force strings to literal cells. '=' in a note must never become an
            # executable Excel formula, and leading zeroes in IDs must survive.
            if isinstance(value, str):
                if len(value) > 32767 or ILLEGAL_CHARACTERS_RE.search(value):
                    raise ValidationError(f"{title}: a text value cannot be represented in Excel.")
            cell = sheet.cell(number, column, value)
            if isinstance(value, str):
                cell.data_type = "s"
    sheet.freeze_panes = f"D{header_row + 1}"
    sheet.auto_filter.ref = f"A{header_row}:{get_column_letter(len(columns))}{sheet.max_row}"
    for cell in sheet[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="245567")
        sheet.column_dimensions[get_column_letter(cell.column)].width = min(
            max(len(cell.value) + 2, 18), 38
        )
    if title == "Grids":
        start = 1
        for index, (_, names) in enumerate(GRID_GROUPS):
            heading, body = GROUP_COLORS[index % len(GROUP_COLORS)]
            finish = start + len(names) - 1
            for cells in sheet.iter_rows(min_col=start, max_col=finish):
                for cell in cells:
                    cell.fill = PatternFill("solid", fgColor=heading if cell.row <= 2 else body)
                    if cell.row <= 2:
                        cell.font = Font(bold=True, color="FFFFFF")
            start = finish + 1
    elif title == "Sessions":
        # Portable identity is transfer metadata, not something a colleague types.
        sheet.column_dimensions["B"].hidden = True


def export_workbook(*, actor, grids):
    current_staff(actor)
    # Enforce archive exclusion even when called outside the registry view.
    grids = list(
        grids.active().select_related("session__owner", "session__prepared_by")[: MAX_ROWS + 1]
    )
    if len(grids) > MAX_ROWS:
        raise ValidationError(f"Please narrow your filters to at most {MAX_ROWS} grids.")
    rows, owners, sessions = [], {}, {}
    for grid in grids:
        session, owner = grid.session, grid.session.owner
        key = f"session-{session.pk}"
        row = {name: getattr(grid, name) for name in PREPARATION_FIELDS}
        row.update(
            grid_number=grid.grid_number,
            owner_name=owner.name,
            owner_code=owner.code,
            session_key=key,
            prepared_by=session.prepared_by.username if session.prepared_by else "",
            prepared_at=session.prepared_at.isoformat() if session.prepared_at else "",
            experiment_reference=session.experiment_reference,
            project_reference=session.project_reference,
            session_notes=session.notes,
        )
        rows.append(row)
        owners[owner.pk] = {name: getattr(owner, name) for name, _ in OWNER_COLUMNS}
        sessions[key] = {
            "session_label": key,
            "session_key": str(session.request_token),
            "defaults_schema_version": session.defaults_schema_version,
            "defaults": json.dumps(session.defaults, ensure_ascii=False),
        }
    book = Workbook()
    book.remove(book.active)
    _write_sheet(book, "Grids", GRID_COLUMNS, rows)
    _write_sheet(book, "Owners", OWNER_COLUMNS, owners.values())
    _write_sheet(book, "Sessions", SESSION_COLUMNS, sessions.values())
    instructions = book.create_sheet("Read me")
    for text in [
        FORMAT_MARKER,
        "Grids contains all preparation columns for the filtered selection, across all pages.",
        "Owners describes the sample owners. Import creates missing owners, never login accounts.",
        "Session groups rows from one preparation. For hand entry, use labels such as session-1.",
        "Hand entry needs Grids and Owners. Leave Sessions empty; internal keys are automatic.",
        "Exported Sessions metadata preserves portable identities; do not edit its hidden keys.",
        "Sessions preserves original defaults independently of edited grid values.",
        "Dates YYYY-MM-DD default to 12:00 Europe/Stockholm; timestamps include a UTC offset.",
        "Blank dates/measurements remain unknown; 0 is zero.",
        "Import previews new/existing records and conflicts. It never overwrites existing records.",
        "Unknown operator logins remain unknown; import never assigns them to the uploader.",
        "Deleted records, physical events, access grants and audit history are not exported.",
        "Copied-from relationships are not part of this transfer format.",
        "This transfers current records. It is not a database backup or the legacy layout.",
        "Keep laboratory workbooks private; do not add them to Git.",
    ]:
        instructions.append([text])
    instructions.column_dimensions["A"].width = 115
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def read_workbook(stream, *, filename="workbook.xlsx"):
    """Read only the documented current format; never evaluate formulas."""
    content = stream.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValidationError("The workbook must be no larger than 5 MB.")
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_UNPACKED_BYTES:
                raise ValidationError("The expanded workbook is too large.")
        book = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
    except (BadZipFile, InvalidFileException, ValueError, KeyError, ParseError) as error:
        raise ValidationError("Upload a valid .xlsx workbook exported by this registry.") from error
    try:
        if "Read me" in book and book["Read me"]["A1"].value != FORMAT_MARKER:
            raise ValidationError(
                "This is not a current registry export. Use an exported template."
            )
        payload = {"filename": filename[:200], "sha256": hashlib.sha256(content).hexdigest()}
        for title, columns in SHEETS.items():
            if title not in book:
                if title == "Sessions":
                    payload["sessions"] = []
                    continue
                raise ValidationError(f"Missing worksheet: {title}.")
            sheet = book[title]
            header_row = 2 if title == "Grids" else 1
            if sheet.max_row > MAX_ROWS + header_row or sheet.max_column > len(columns):
                raise ValidationError(f"{title}: unexpected columns or more than {MAX_ROWS} rows.")
            rows = sheet.iter_rows(min_row=header_row)
            headers = [cell.value for cell in next(rows)]
            if headers != [label for _, label in columns]:
                raise ValidationError(f"{title}: column headings must match the exported template.")
            records = []
            for number, cells in enumerate(rows, header_row + 1):
                if any(cell.data_type in ("f", "e") for cell in cells):
                    raise ValidationError(
                        f"{title} row {number}: formula/error cells are not allowed."
                    )
                if all(cell.value in (None, "") for cell in cells):
                    continue
                record = {}
                for (key, _), cell in zip(columns, cells, strict=True):
                    value = cell.value
                    # Excel often converts a typed date into a midnight datetime.
                    # Respect date-only formatting without discarding a real time.
                    if (
                        key == "prepared_at"
                        and isinstance(value, datetime)
                        and value.time() == time.min
                        and is_datetime(cell.number_format) == "date"
                    ):
                        value = value.date().isoformat()
                    record[key] = value
                # JSON-safe values let a server-side session retain the preview.
                record = {
                    key: value if isinstance(value, bool) or value is None else str(value)
                    for key, value in record.items()
                }
                record["_row"] = number
                records.append(record)
            payload[title.lower()] = records
        return payload
    except (BadZipFile, ValueError, KeyError, ParseError, StopIteration) as error:
        raise ValidationError("The workbook is damaged or has missing/invalid cells.") from error
    finally:
        book.close()
