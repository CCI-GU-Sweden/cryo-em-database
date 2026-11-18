"""Conservative workbook parsing for optional vocabulary, never physical records.

Raw source values and cell references stay in the local database. No private
suggestions are embedded in source code or fixtures.
"""

import hashlib
import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from openpyxl import load_workbook

from .models import AuditEvent, Grid, PreparationSuggestion
from .preparation import compact_decimal, normalize_preparation_text

NUMBER = r"[+-]?\d+(?:\.\d+)?"


def workbook_suggestions(path):
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    candidates, warnings = {}, []
    counts = {"populated_rows": 0, "identifier_only_rows": 0}
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        sheet = book["Sheet1"]
        if sheet.cell(3, 1).value != "Grid number" or sheet.cell(3, 3).value != "Sample":
            raise ValidationError("The workbook does not match the expected multirow headers.")

        def add(field, value, cell):
            if value is None or value == "":
                return
            try:
                cleaned = Grid._meta.get_field(field).clean(
                    normalize_preparation_text(field, value), Grid()
                )
            except ValidationError:
                warnings.append(f"{cell.coordinate}: value requires review; not suggested.")
                return
            text = str(compact_decimal(cleaned))
            if len(text) > 500:
                warnings.append(
                    f"{cell.coordinate}: value exceeds suggestion length; not suggested."
                )
                return
            candidates.setdefault(
                (field, text),
                {
                    "filename": path.name,
                    "sha256": checksum,
                    "sheet": sheet.title,
                    "cell": cell.coordinate,
                    "raw_value": str(cell.value),
                },
            )

        for row in sheet.iter_rows(min_row=4):
            # Identifier-only template rows never produce suggestions or grids.
            if not row[0].value:
                continue
            if not any(cell.value not in (None, "") for cell in row[2:15]):
                counts["identifier_only_rows"] += 1
                continue
            counts["populated_rows"] += 1
            for index, field in {
                2: "sample_description",
                4: "buffer_description",
                6: "carbon_description",
                28: "notes",
            }.items():
                cell = row[index]
                if cell.data_type == "f":
                    warnings.append(f"{cell.coordinate}: formula not evaluated; requires review.")
                else:
                    add(field, cell.value, cell)
            cell = row[3]
            concentration = re.fullmatch(
                rf"\s*({NUMBER})\s*(mg/ml|mg/mL|µg/ml|µg/mL)\s*", str(cell.value)
            )
            if concentration:
                add("sample_concentration_value", Decimal(concentration[1]), cell)
                add("sample_concentration_unit", concentration[2].replace("/ml", "/mL"), cell)
            elif cell.value is not None:
                warnings.append(f"{cell.coordinate}: concentration requires review.")
            cell = row[5]
            if cell.value and cell.data_type != "f":
                grid_type = re.fullmatch(r"(.+?)\s*\(([^()]*)\)\s*", str(cell.value))
                add("grid_type", grid_type[1].strip() if grid_type else cell.value, cell)
                if grid_type:
                    # The parenthetical value has no confirmed meaning and is not a batch.
                    warnings.append(
                        f"{cell.coordinate}: parenthetical grid reference not suggested."
                    )
            cell = row[7]
            glow = re.fullmatch(
                rf"\s*([^,]+),\s*([^,]+),\s*({NUMBER})\s*mA,\s*({NUMBER})\s*s\s*", str(cell.value)
            )
            if glow:
                for field, value in zip(
                    ["glow_atmosphere", "glow_polarity", "glow_current_ma", "glow_duration_s"],
                    [glow[1].strip(), glow[2].strip(), Decimal(glow[3]), Decimal(glow[4])],
                ):
                    add(field, value, cell)
            elif cell.value is not None:
                warnings.append(f"{cell.coordinate}: glow discharge requires review.")
            for index, field, unit in [
                (8, "sample_volume_ul", r"[µμu]l"),
                (9, "temperature_c", r"°C"),
                (11, "blot_time_s", "s"),
                (12, "hold_time_s", "s"),
                (13, "blot_force", ""),
            ]:
                cell = row[index]
                value = re.fullmatch(rf"\s*({NUMBER})\s*{unit}\s*", str(cell.value))
                if value:
                    add(field, Decimal(value[1]), cell)
                elif cell.value is not None:
                    warnings.append(f"{cell.coordinate}: measurement requires review.")
    finally:
        book.close()
    return candidates, warnings, checksum, counts


@transaction.atomic
def save_suggestions(candidates, checksum):
    created = 0
    for (field, value), source in candidates.items():
        _, new = PreparationSuggestion.objects.get_or_create(
            field_name=field, value=value, defaults={"source": source}
        )
        created += int(new)
    if created:
        AuditEvent.objects.create(
            entity_type="PreparationSuggestion",
            entity_id=checksum,
            operation="seed_suggestions",
            source="workbook",
            changes={"created": created, "source_sha256": checksum},
        )
    return created
