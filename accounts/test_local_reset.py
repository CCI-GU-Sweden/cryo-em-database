"""Exercise the reset only against Django's disposable PostgreSQL test database."""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import psycopg
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TransactionTestCase, override_settings
from psycopg import sql

from cci_grids.models import SampleOwner
from cci_grids.storage_models import GridBoxType, Puck
from scripts.runtime import find_tool


class LocalResetTests(TransactionTestCase):
    def test_clear_users_option_removes_accounts(self):
        with connection.cursor() as cursor:
            cursor.execute("SHOW data_directory")
            cluster = Path(cursor.fetchone()[0])
        get_user_model().objects.create_user(username="reset-user", role="staff")
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory) / ".local"
            local.mkdir()
            (local / "postgres").symlink_to(cluster, target_is_directory=True)
            with (
                override_settings(BASE_DIR=Path(directory)),
                patch("builtins.input", return_value="reset"),
            ):
                call_command("reset_local_registry", clear_users=True)
        self.assertFalse(get_user_model().objects.exists())

    def test_rejects_nonlocal_target_before_confirmation(self):
        with override_settings(ROOT_URLCONF="not_the_local_host"):
            with self.assertRaisesMessage(CommandError, "standalone local PostgreSQL"):
                call_command("reset_local_registry")

    def test_cancelled_confirmation_does_not_modify_database(self):
        with connection.cursor() as cursor:
            cursor.execute("SHOW data_directory")
            cluster = Path(cursor.fetchone()[0])
        owner = SampleOwner.objects.create(name="Keep me", code="keep")
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory) / ".local"
            local.mkdir()
            (local / "postgres").symlink_to(cluster, target_is_directory=True)
            with (
                override_settings(BASE_DIR=Path(directory)),
                patch("builtins.input", return_value="no"),
            ):
                with self.assertRaisesMessage(CommandError, "confirmation did not match"):
                    call_command("reset_local_registry")
        self.assertTrue(SampleOwner.objects.filter(pk=owner.pk).exists())

    def test_reset_retains_templates_and_users_and_creates_restorable_backup(self):
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))
        with connection.cursor() as cursor:
            cursor.execute("SHOW data_directory")
            cluster = Path(cursor.fetchone()[0])
        user = get_user_model().objects.create_user(username="reset-test", role="staff")
        SampleOwner.objects.create(name="Reset test owner", code="rtow")
        types = GridBoxType.objects.count()
        pucks = Puck.objects.count()
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory) / ".local"
            local.mkdir()
            (local / "postgres").symlink_to(cluster, target_is_directory=True)
            with override_settings(BASE_DIR=Path(directory)):
                with patch("builtins.input", return_value="reset"):
                    call_command("reset_local_registry")
            archives = list((local / "backups").glob("*.dump"))
            self.assertEqual(len(archives), 1)
            restore_name = connection.settings_dict["NAME"] + "_reset_restore"
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE DATABASE {} ").format(sql.Identifier(restore_name)))
            try:
                db = connection.settings_dict
                env = os.environ.copy()
                env["PGPASSWORD"] = db["PASSWORD"]
                subprocess.run(
                    [
                        str(find_tool("pg_restore")),
                        "--exit-on-error",
                        "--no-owner",
                        "--host",
                        db["HOST"],
                        "--port",
                        str(db["PORT"]),
                        "--username",
                        db["USER"],
                        "--dbname",
                        restore_name,
                        str(archives[0]),
                    ],
                    env=env,
                    check=True,
                )
                with psycopg.connect(
                    host=db["HOST"],
                    port=db["PORT"],
                    user=db["USER"],
                    password=db["PASSWORD"],
                    dbname=restore_name,
                ) as restored:
                    self.assertEqual(
                        restored.execute(
                            "SELECT count(*) FROM registry_sampleowner WHERE code = %s", ("rtow",)
                        ).fetchone()[0],
                        1,
                    )
            finally:
                with connection.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("DROP DATABASE {} ").format(sql.Identifier(restore_name))
                    )
        self.assertFalse(SampleOwner.objects.exists())
        self.assertTrue(get_user_model().objects.filter(pk=user.pk).exists())
        self.assertEqual(GridBoxType.objects.count(), types)
        self.assertEqual(Puck.objects.count(), pucks)
        self.assertFalse(Puck.objects.exclude(in_dewar=False).exists())
