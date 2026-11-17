"""Generate a field/type reference from Django's authoritative Grid model."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models

from cci_grids.models import Grid

START = "<!-- generated-grid-fields:start -->"
END = "<!-- generated-grid-fields:end -->"


def field_reference():
    rows = [
        "| Field | PostgreSQL type | NULL allowed | Empty text allowed | "
        "Application default | Model bounds |",
        "|---|---|---|---|---|---|",
    ]
    for field in Grid._meta.fields:
        if isinstance(field, models.AutoField):
            default = "Generated ID"
        elif getattr(field, "auto_now", False):
            default = "Time of save"
        elif getattr(field, "auto_now_add", False):
            default = "Time of creation"
        elif field.has_default():
            default = str(field.default)
        else:
            default = "—"
        bounds = []
        for validator in field.validators:
            if isinstance(validator, MinValueValidator):
                bounds.append(f">= {validator.limit_value}")
            elif isinstance(validator, MaxValueValidator):
                bounds.append(f"<= {validator.limit_value}")
        empty_text = field.blank and isinstance(field, (models.CharField, models.TextField))
        rows.append(
            f"| `{field.column}` | `{field.db_type(connection)}` | "
            f"{'Yes' if field.null else 'No'} | {'Yes' if empty_text else 'No'} | "
            f"{default} | {', '.join(bounds) or '—'} |"
        )
    return "\n".join(rows)


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--update-docs", action="store_true")
        group.add_argument("--check", action="store_true")

    def handle(self, *args, **options):
        table = field_reference()
        if not (options["update_docs"] or options["check"]):
            self.stdout.write(table)
            return
        path = Path(settings.BASE_DIR) / "docs" / "02_SCHEMA_V0_1.md"
        original = path.read_text()
        block = f"{START}\n{table}\n{END}"
        if START in original and END in original:
            begin, finish = original.index(START), original.index(END) + len(END)
            updated = original[:begin] + block + original[finish:]
        else:
            updated = original.rstrip() + "\n\n" + block + "\n"
        if options["check"]:
            if original != updated:
                raise CommandError(
                    "Grid field reference is outdated. Run describe_grid_fields --update-docs."
                )
            self.stdout.write("Grid field reference matches the model.")
        else:
            path.write_text(updated)
            self.stdout.write(
                "Updated the generated Grid field reference in docs/02_SCHEMA_V0_1.md."
            )
