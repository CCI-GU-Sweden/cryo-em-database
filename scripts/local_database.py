"""Manage a private prototype PostgreSQL cluster using the active Conda tools.

This helper never deletes a cluster. It is intended for loopback development,
not shared hosting. Docker users can use compose.yaml instead.
"""

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql

if __package__:
    from .runtime import find_tool
else:
    # Support both direct script execution and importing this module for tests.
    from runtime import find_tool

ROOT = Path(__file__).resolve().parent.parent
CLUSTER = ROOT / ".local" / "postgres"


def run_tool(name: str, *arguments: str) -> None:
    subprocess.run([str(find_tool(name)), *arguments], check=True)


def initialize_cluster(user: str, password: str) -> None:
    # Close before initdb reads the file: Windows does not permit the original
    # open-file sharing pattern. The context removes it even if initdb fails.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete_on_close=False
    ) as password_file:
        password_file.write(password + "\n")
        password_file.close()
        run_tool(
            "initdb",
            "-D",
            str(CLUSTER),
            "-U",
            user,
            "--auth=scram-sha-256",
            "--encoding=UTF8",
            "--locale=C",
            f"--pwfile={password_file.name}",
        )


def server_options(cluster: Path, port: int, *, windows: bool | None = None) -> str:
    """pg_ctl forwards this string to postgres; quote Unix paths with spaces."""
    windows = os.name == "nt" if windows is None else windows
    options = f"-h 127.0.0.1 -p {port}"
    if not windows:
        options += f" -k {shlex.quote(str(cluster))}"
    return options


def cluster_is_running() -> bool:
    """pg_ctl status uses 3 for stopped; other errors must remain failures."""
    result = subprocess.run(
        [str(find_tool("pg_ctl")), "-D", str(CLUSTER), "status"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    # Inaccessible/invalid directories (status 4), permission failures and other
    # unexpected errors must not be reported as a successful stop.
    if result.returncode not in (0, 3):
        if result.stdout:
            print(result.stdout, end="", file=sys.stderr)
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        result.check_returncode()
    return result.returncode == 0


def stop_cluster() -> None:
    if not CLUSTER.exists():
        print(f"No local database directory in this checkout ({CLUSTER}); nothing to stop.")
        return
    if not cluster_is_running():
        print(f"Local database is already stopped for this checkout ({CLUSTER}).")
        return
    try:
        run_tool("pg_ctl", "-D", str(CLUSTER), "-w", "stop")
    except subprocess.CalledProcessError:
        # The server can exit between the status check and the stop command.
        # Accept that final state, but never hide a failed stop of a running server.
        if cluster_is_running():
            raise
        print(f"Local database is no longer running for this checkout ({CLUSTER}).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)

    if args.action == "stop":
        stop_cluster()
        return
    if args.action == "status":
        if not CLUSTER.exists():
            print(f"No local database directory in this checkout ({CLUSTER}).")
        else:
            state = "running" if cluster_is_running() else "stopped"
            print(f"Local database is {state} for this checkout ({CLUSTER}).")
        return

    user = os.environ.get("POSTGRES_USER", "cci")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    database = os.environ.get("POSTGRES_DB", "cci_prototype")
    port = int(os.environ.get("POSTGRES_PORT", "5433"))
    if not password:
        parser.error("Set POSTGRES_PASSWORD in your private .env before starting PostgreSQL.")

    CLUSTER.parent.mkdir(exist_ok=True)
    if not (CLUSTER / "PG_VERSION").exists():
        initialize_cluster(user, password)

    if not cluster_is_running():
        # TCP is loopback-only. Unix also uses a socket in the private cluster;
        # native Windows needs no Unix-socket directory.
        run_tool(
            "pg_ctl",
            "-D",
            str(CLUSTER),
            "-l",
            str(CLUSTER.parent / "postgres.log"),
            "-o",
            server_options(CLUSTER, port),
            "-w",
            "start",
        )

    with psycopg.connect(
        host="127.0.0.1",
        port=port,
        user=user,
        password=password,
        dbname="postgres",
        autocommit=True,
    ) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
        ).fetchone()
        if not exists:
            # Database names are SQL identifiers, not string values.
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    print(f"Local prototype database is ready at 127.0.0.1:{port}.")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        raise SystemExit(str(error)) from error
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            f"PostgreSQL command failed (exit {error.returncode}); see output above."
        ) from error
