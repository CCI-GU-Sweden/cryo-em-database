"""Explicitly clear disposable local registry data, preserving inventory templates."""

import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from cci_grids.storage_models import Puck
from scripts.runtime import find_tool

TABLES = (
    "registry_gridevent",
    "registry_boxevent",
    "registry_puckevent",
    "registry_gridslot",
    "registry_gridbox",
    "registry_deletedgrid",
    "registry_grid",
    "registry_preparationsession",
    "registry_owneraccessgrant",
    "registry_sampleowner",
    "registry_auditevent",
    "registry_preparationsuggestion",
    "registry_grididentifiercounter",
)


def backup_database(database):
    """Save and inspect a compressed PostgreSQL archive before any reset."""
    directory = Path(settings.BASE_DIR) / ".local" / "backups"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    env = os.environ.copy()
    env["PGPASSWORD"] = str(database.get("PASSWORD") or "")
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"registry-before-reset-{stamp}-", suffix=".dump", dir=directory, delete=False
        ) as archive:
            path = Path(archive.name)
            try:
                subprocess.run(
                    [
                        str(find_tool("pg_dump")),
                        "--format=custom",
                        "--no-password",
                        "--host",
                        database["HOST"],
                        "--port",
                        str(database["PORT"]),
                        "--username",
                        database["USER"],
                        "--dbname",
                        database["NAME"],
                    ],
                    stdout=archive,
                    env=env,
                    check=True,
                )
            except Exception:
                archive.close()
                path.unlink(missing_ok=True)
                raise
        subprocess.run(
            [str(find_tool("pg_restore")), "--list", str(path)],
            stdout=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise CommandError("Backup failed; no reset was performed.") from error
    return path


class Command(BaseCommand):
    help = "Clear the disposable local registry, retaining configured locations and box types."

    def add_arguments(self, parser):
        parser.add_argument("--clear-users", action="store_true", help="Also remove local users.")

    def handle(self, *args, **options):
        database = connection.settings_dict
        if (
            connection.vendor != "postgresql"
            or settings.ROOT_URLCONF != "config.urls"
            or database.get("HOST") not in {"127.0.0.1", "localhost", "::1"}
        ):
            raise CommandError("Reset is available only for the standalone local PostgreSQL setup.")
        expected = (Path(settings.BASE_DIR) / ".local" / "postgres").resolve()
        with connection.cursor() as cursor:
            cursor.execute("SHOW data_directory")
            actual = Path(cursor.fetchone()[0]).resolve()
        if actual != expected:
            raise CommandError("The database is not running from this checkout's local cluster.")

        name = database["NAME"]
        self.stdout.write(f"Target: local database {name} in {actual}")
        self.stdout.write("This removes registry data and history, keeping types and locations.")
        if options["clear_users"]:
            self.stdout.write("All local users and login sessions will also be removed.")
        try:
            answer = input("Type reset to continue: ")
        except EOFError as error:
            raise CommandError("Reset cancelled: confirmation is required.") from error
        if answer != "reset":
            raise CommandError("Reset cancelled: confirmation did not match.")

        backup = backup_database(database)
        self.stdout.write(f"Database backup saved to {backup}")
        with transaction.atomic():
            with connection.cursor() as cursor:
                # No CASCADE: unexpected foreign keys must stop the reset instead
                # of expanding it to tables belonging to other applications.
                names = ", ".join(connection.ops.quote_name(table) for table in TABLES)
                cursor.execute(f"TRUNCATE TABLE {names} RESTART IDENTITY")
            Puck.objects.update(in_dewar=False, version=1)
            if options["clear_users"]:
                Session.objects.all().delete()
                get_user_model().objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Local registry reset complete."))
