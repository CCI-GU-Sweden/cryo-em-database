"""Launcher portability without requiring Windows or changing a real database."""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
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


class DatabaseStopTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cluster = Path(directory.name) / "project with spaces" / "postgres"
        cluster_patch = patch.object(local_database, "CLUSTER", self.cluster)
        cluster_patch.start()
        self.addCleanup(cluster_patch.stop)
        tool_patch = patch.object(local_database, "find_tool", return_value=Path("pg_ctl"))
        tool_patch.start()
        self.addCleanup(tool_patch.stop)

    def test_stop_before_initialization_does_not_run_or_create_anything(self):
        with patch.object(local_database, "run_tool") as run, redirect_stdout(StringIO()) as output:
            local_database.stop_cluster()
        run.assert_not_called()
        self.assertIn("nothing to stop", output.getvalue())
        self.assertFalse(self.cluster.exists())

    def test_stopped_cluster_returns_success_without_calling_stop(self):
        self.cluster.mkdir(parents=True)
        stopped = subprocess.CompletedProcess(["pg_ctl"], 3, stdout="no server running", stderr="")
        with patch.object(local_database.subprocess, "run", return_value=stopped) as command:
            with redirect_stdout(StringIO()) as output:
                local_database.stop_cluster()
                local_database.stop_cluster()
        self.assertIn("already stopped", output.getvalue())
        self.assertEqual(command.call_count, 2)
        self.assertTrue(all(call.args[0][-1] == "status" for call in command.call_args_list))

    def test_running_cluster_uses_its_own_directory_and_waits_for_shutdown(self):
        self.cluster.mkdir(parents=True)
        with patch.object(local_database, "cluster_is_running", return_value=True):
            with patch.object(local_database, "run_tool") as run:
                local_database.stop_cluster()
        run.assert_called_once_with("pg_ctl", "-D", str(self.cluster), "-w", "stop")

    def test_status_permission_and_directory_errors_remain_failures(self):
        self.cluster.mkdir(parents=True)
        for code in (1, 4):
            result = subprocess.CompletedProcess(
                ["pg_ctl"], code, stdout="", stderr="Cannot access directory"
            )
            with (
                self.subTest(code=code),
                patch.object(local_database.subprocess, "run", return_value=result),
            ):
                with redirect_stderr(StringIO()) as errors, redirect_stdout(StringIO()) as output:
                    with self.assertRaises(subprocess.CalledProcessError):
                        local_database.stop_cluster()
            self.assertIn("Cannot access directory", errors.getvalue())
            self.assertNotIn("already stopped", output.getvalue())

    def test_a_server_exiting_during_stop_is_success(self):
        self.cluster.mkdir(parents=True)
        with patch.object(local_database, "cluster_is_running", side_effect=[True, False]):
            with patch.object(
                local_database, "run_tool", side_effect=subprocess.CalledProcessError(1, ["pg_ctl"])
            ):
                with redirect_stdout(StringIO()) as output:
                    local_database.stop_cluster()
        self.assertIn("no longer running", output.getvalue())

    def test_failed_stop_is_not_hidden_if_the_server_is_still_running(self):
        self.cluster.mkdir(parents=True)
        with patch.object(local_database, "cluster_is_running", return_value=True):
            with patch.object(
                local_database, "run_tool", side_effect=subprocess.CalledProcessError(1, ["pg_ctl"])
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    local_database.stop_cluster()

    def test_stale_pid_file_is_not_deleted_or_used_for_a_forced_kill(self):
        self.cluster.mkdir(parents=True)
        pid = self.cluster / "postmaster.pid"
        pid.write_text("123456\n")
        with patch.object(local_database, "cluster_is_running", return_value=False):
            with patch.object(local_database, "run_tool") as run, redirect_stdout(StringIO()):
                local_database.stop_cluster()
        self.assertEqual(pid.read_text(), "123456\n")
        run.assert_not_called()

    def test_status_reports_stopped_without_initialization(self):
        with patch.object(sys, "argv", ["local_database.py", "status"]):
            with patch.object(local_database, "load_dotenv"), redirect_stdout(StringIO()) as output:
                local_database.main()
        self.assertIn("No local database directory", output.getvalue())
        self.assertFalse(self.cluster.exists())

    def test_dev_stop_succeeds_in_a_fresh_checkout(self):
        # Exercise the real two-process entry point against a temporary empty
        # checkout, so this test cannot stop the developer's own database.
        root = Path(__file__).resolve().parent.parent
        checkout = self.cluster.parent
        scripts = checkout / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy(root / "dev.py", checkout / "dev.py")
        for name in ("__init__.py", "runtime.py", "local_database.py"):
            shutil.copy(root / "scripts" / name, scripts / name)
        result = subprocess.run(
            [sys.executable, "dev.py", "stop"], cwd=checkout, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nothing to stop", result.stdout)
        self.assertNotIn("Traceback", result.stderr)
