"""Launcher portability without requiring Windows or changing a real database."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from . import local_database
from .runtime import find_tool


class ToolDiscoveryTests(TestCase):
    def test_windows_conda_postgresql_and_ruff_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "Conda environment with spaces"
            postgres = prefix / "Library" / "bin" / "initdb.exe"
            ruff = prefix / "Scripts" / "ruff.exe"
            for tool in (postgres, ruff):
                tool.parent.mkdir(parents=True, exist_ok=True)
                tool.touch()
            self.assertEqual(find_tool("initdb", prefix=prefix, windows=True), postgres)
            self.assertEqual(find_tool("ruff", prefix=prefix, windows=True), ruff)

    def test_unix_conda_tools_still_use_bin(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            tool = prefix / "bin" / "pg_ctl"
            tool.parent.mkdir()
            tool.touch()
            self.assertEqual(find_tool("pg_ctl", prefix=prefix, windows=False), tool)

    def test_missing_tool_never_uses_another_installation_on_path(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "active"
            other = Path(directory) / "other"
            other.mkdir()
            (other / "initdb.exe").touch()
            with patch.dict(os.environ, {"PATH": str(other)}):
                with self.assertRaisesRegex(FileNotFoundError, "environment.yml"):
                    find_tool("initdb", prefix=prefix, windows=True)


class DatabaseLaunchTests(TestCase):
    def test_initdb_reads_a_closed_password_file_and_removes_it_afterward(self):
        real_temporary_file = tempfile.NamedTemporaryFile
        files = []
        password = "synthetic-test-password"

        def create_file(**kwargs):
            file = real_temporary_file(**kwargs)
            files.append(file)
            return file

        def inspect_command(name, *arguments):
            self.assertEqual(name, "initdb")
            self.assertTrue(files[0].file.closed)
            path = Path(
                next(
                    arg.removeprefix("--pwfile=")
                    for arg in arguments
                    if arg.startswith("--pwfile=")
                )
            )
            self.assertEqual(path.read_text(encoding="utf-8"), password + "\n")
            self.assertNotIn(password, " ".join(arguments))

        with patch.object(local_database.tempfile, "NamedTemporaryFile", side_effect=create_file):
            with patch.object(local_database, "run_tool", side_effect=inspect_command):
                local_database.initialize_cluster("synthetic-user", password)
        self.assertFalse(Path(files[0].name).exists())

    def test_password_file_is_removed_if_initialization_fails(self):
        paths = []

        def fail(name, *arguments):
            paths.append(
                Path(
                    next(
                        arg.removeprefix("--pwfile=")
                        for arg in arguments
                        if arg.startswith("--pwfile=")
                    )
                )
            )
            raise subprocess.CalledProcessError(1, [name])

        with patch.object(local_database, "run_tool", side_effect=fail):
            with self.assertRaises(subprocess.CalledProcessError):
                local_database.initialize_cluster("synthetic-user", "synthetic-password")
        self.assertFalse(paths[0].exists())

    def test_windows_uses_loopback_without_a_unix_socket_path(self):
        options = local_database.server_options(Path("path with spaces"), 5433, windows=True)
        self.assertEqual(options, "-h 127.0.0.1 -p 5433")

    def test_unix_socket_path_with_spaces_and_apostrophes_survives_quoting(self):
        cluster = Path("/tmp/colleague's project/postgres")
        options = local_database.server_options(cluster, 5433, windows=False)
        self.assertEqual(
            shlex.split(options), ["-h", "127.0.0.1", "-p", "5433", "-k", str(cluster)]
        )
