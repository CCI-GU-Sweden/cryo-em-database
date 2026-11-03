"""Manage a private prototype PostgreSQL cluster using the active Conda tools.

This helper never deletes a cluster. It is intended for loopback development,
not shared hosting. Docker users can use compose.yaml instead.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
CLUSTER = ROOT / ".local" / "postgres"
TOOLS = Path(sys.executable).parent


def run_tool(name: str, *arguments: str) -> None:
    subprocess.run([str(TOOLS / name), *arguments], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)

    if args.action != "start":
        run_tool("pg_ctl", "-D", str(CLUSTER), args.action)
        return

    user = os.environ.get("POSTGRES_USER", "cci")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    database = os.environ.get("POSTGRES_DB", "cci_prototype")
    port = int(os.environ.get("POSTGRES_PORT", "5433"))
    if not password:
        parser.error("Set POSTGRES_PASSWORD in your private .env before starting PostgreSQL.")

    CLUSTER.parent.mkdir(exist_ok=True)
    if not (CLUSTER / "PG_VERSION").exists():
        # initdb accepts a password file. A private temporary file keeps the
        # password out of process arguments and is removed immediately afterward.
        with tempfile.NamedTemporaryFile(mode="w") as password_file:
            password_file.write(password + "\n")
            password_file.flush()
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

    status = subprocess.run(
        [str(TOOLS / "pg_ctl"), "-D", str(CLUSTER), "status"],
        capture_output=True,
    )
    if status.returncode != 0:
        # TCP is loopback-only; put the Unix socket in the private cluster too.
        run_tool(
            "pg_ctl",
            "-D",
            str(CLUSTER),
            "-l",
            str(CLUSTER.parent / "postgres.log"),
            "-o",
            f"-h 127.0.0.1 -p {port} -k {CLUSTER}",
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
    main()
