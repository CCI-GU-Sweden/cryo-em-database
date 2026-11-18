"""Test an installed registry wheel against a real dashboard checkout on PostgreSQL.

Run with the dashboard's Python environment after installing the wheel's dependencies.
PGHOST, PGPORT, PGUSER, PGPASSWORD and PGDATABASE select the PostgreSQL server.
Django creates and destroys a uniquely named test database; existing records are untouched.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

SETTINGS = """
from dashboard.settings import *

# Mirror the contract's three-line registration without modifying the host checkout.
if 'cci_grids.apps.RegistryConfig' not in INSTALLED_APPS and 'cci_grids' not in INSTALLED_APPS:
    INSTALLED_APPS.append('cci_grids.apps.RegistryConfig')
if 'cci_grids.dashboard_module.module' not in DASHBOARD_MODULES:
    DASHBOARD_MODULES.append('cci_grids.dashboard_module.module')
CCI_GRIDS_DASHBOARD = True
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
# Deliberately differ from the facility zone to exercise module-owned localization.
TIME_ZONE = 'UTC'
DATABASES['default']['TEST'] = {'NAME': TEST_DATABASE}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--dashboard", type=Path, required=True)
    arguments = parser.parse_args()
    wheel = arguments.wheel.resolve(strict=True)
    dashboard = arguments.dashboard.resolve(strict=True)
    if not (dashboard / "MODULE_CONTRACT.md").is_file():
        parser.error("--dashboard must point to the dashboard checkout.")
    if not os.environ.get("PGHOST"):
        parser.error("Set PGHOST and the other PostgreSQL connection variables first.")

    test_database = "test_cci_dashboard_" + uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="cci-dashboard-contract-") as directory:
        root = Path(directory)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                directory,
                str(wheel),
            ],
            check=True,
        )
        (root / "contract_settings.py").write_text(
            f"TEST_DATABASE = {test_database!r}\n" + SETTINGS
        )
        (root / "core_settings.py").write_text(
            "from dashboard.settings import *\n"
            "ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']\n"
            f"DATABASES['default']['TEST'] = {{'NAME': {test_database + '_core'!r}}}\n"
            "PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']\n"
        )
        shutil.copyfile(
            Path(__file__).with_name("dashboard_contract_tests.py"),
            root / "dashboard_contract_tests.py",
        )
        environment = dict(os.environ)
        environment.update(
            {
                "PYTHONPATH": os.pathsep.join([directory, str(dashboard)]),
                "DJANGO_SETTINGS_MODULE": "contract_settings",
                "DJANGO_SECRET_KEY": uuid4().hex,
                "DJANGO_DEBUG": "1",
                "ORCID_ENVIRONMENT": "sandbox",
                "ORCID_CLIENT_ID": "",
                "ORCID_CLIENT_SECRET": "",
                "DASHBOARD_UPLOADS_ENABLED": "0",
                "DASHBOARD_OMERO_ENABLED": "0",
                "DASHBOARD_TICKETS_ENABLED": "0",
                "DASHBOARD_GRIDS_ENABLED": "0",
                "CCI_CONTRACT_DASHBOARD": str(dashboard),
                "CCI_CONTRACT_INSTALLATION": directory,
            }
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "django",
                "test",
                "dashboard_contract_tests",
                "cci_grids.test_owner_administration",
                "cci_grids.test_facility_time",
                "--verbosity",
                "2",
                "--noinput",
            ],
            cwd=directory,
            env=environment,
            check=True,
        )
        # The core suite imports ticket models during discovery, even for skipped
        # tests. Run its standard module configuration in a separate test database;
        # the registry-only browser trial and enabled-module checks stay isolated.
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "core_settings",
                "DASHBOARD_UPLOADS_ENABLED": "1",
                "DASHBOARD_OMERO_ENABLED": "1",
                "DASHBOARD_OMERO_BILLING_ENABLED": "1",
                "DASHBOARD_TICKETS_ENABLED": "1",
            }
        )
        subprocess.run(
            [sys.executable, "-m", "django", "test", "accounts", "--noinput"],
            cwd=directory,
            env=environment,
            check=True,
        )


if __name__ == "__main__":
    main()
