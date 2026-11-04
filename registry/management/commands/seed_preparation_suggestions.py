"""Seed private preparation choices without importing owners, sessions or grids."""

from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from registry.suggestion_import import save_suggestions, workbook_suggestions


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("workbook", type=Path)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            candidates, warnings, checksum, counts = workbook_suggestions(options["workbook"])
        except (OSError, KeyError, ValidationError) as error:
            raise CommandError(str(error)) from error
        for warning in warnings:
            self.stdout.write(warning)
        self.stdout.write(
            f"Read {counts['populated_rows']} populated source rows; "
            f"skipped {counts['identifier_only_rows']} identifier-only template rows."
        )
        self.stdout.write(f"Found {len(candidates)} distinct preparation suggestions.")
        if options["dry_run"]:
            self.stdout.write("Dry run: no database changes.")
        else:
            created = save_suggestions(candidates, checksum)
            self.stdout.write(f"Created {created} suggestions; no grid records were imported.")
