"""One-command launcher for the local prototype: start, check, or stop.

Activate the project's Conda environment first. Every child command uses that
same Python interpreter, so dependencies cannot drift between environments.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_python(*arguments: str) -> None:
    """Stop immediately on failure instead of continuing with an incomplete setup."""
    subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)


def prepare_database() -> None:
    # Both helpers preserve existing settings and data when run again.
    run_python("scripts/configure_local.py")
    run_python("scripts/local_database.py", "start")


def ensure_administrator() -> None:
    """Prompt for credentials only when no active administrator exists."""
    # Import Django after configuration exists; importing settings earlier would
    # fail on a fresh checkout without a .env file.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.contrib.auth import get_user_model

    administrator_exists = (
        get_user_model().objects.filter(is_superuser=True, is_staff=True, is_active=True).exists()
    )
    if not administrator_exists:
        print("\nCreate your first local administrator account.", flush=True)
        run_python("manage.py", "createsuperuser")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="start", choices=["start", "check", "stop"])
    action = parser.parse_args().action

    try:
        if action == "stop":
            run_python("scripts/local_database.py", "stop")
            return 0

        prepare_database()
        if action == "check":
            run_python("manage.py", "check")
            run_python("manage.py", "makemigrations", "--check", "--dry-run")
            run_python("manage.py", "test", "--noinput")
            # Conda installs Ruff as an executable, not an importable Python module.
            ruff = str(Path(sys.executable).parent / "ruff")
            subprocess.run([ruff, "check", "."], cwd=ROOT, check=True)
            subprocess.run([ruff, "format", "--check", "."], cwd=ROOT, check=True)
        else:
            run_python("manage.py", "migrate", "--noinput")
            ensure_administrator()
            print("\nOpen http://127.0.0.1:8000/ in your browser.", flush=True)
            print("Press Ctrl+C to stop the app; PostgreSQL stays running.", flush=True)
            run_python("manage.py", "runserver", "127.0.0.1:8000")
    except KeyboardInterrupt:
        print("\nApp stopped. Run 'python dev.py stop' to stop PostgreSQL too.")
        return 0
    except subprocess.CalledProcessError as error:
        print(f"\nCommand failed (exit {error.returncode}); see the output above.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
