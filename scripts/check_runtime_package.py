"""Verify a built wheel from an installed copy outside the source checkout."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

PROBE = r"""
from pathlib import Path
import django
import sys
import types
from django.conf import settings
settings.configure(
    SECRET_KEY="package-probe-only",
    INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes",
                    "django.contrib.staticfiles", "cci_grids"],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    TEMPLATES=[{"BACKEND": "django.template.backends.django.DjangoTemplates",
                "APP_DIRS": True}],
    STATIC_URL="/static/", ROOT_URLCONF="package_probe_urls",
)
django.setup()
import cci_grids
from cci_grids import excel_import
from cci_grids.models import Grid, PreparationSession
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.management import get_commands
from django.db.migrations.loader import MigrationLoader
from django.template.loader import get_template
from django.urls import include, path, reverse
urls = types.ModuleType("package_probe_urls")
urls.urlpatterns = [path("registry/", include("cci_grids.urls"))]
sys.modules[urls.__name__] = urls
assert reverse("registry:grid_list") == "/registry/"
package = Path(cci_grids.__file__).parent
assert package.is_relative_to(Path.cwd())
assert apps.get_app_config("registry").name == "cci_grids"
assert Grid._meta.db_table == "registry_grid"
assert PreparationSession._meta.get_field("prepared_by").remote_field.model is get_user_model()
assert excel_import.get_user_model() is get_user_model()
loader = MigrationLoader(None)
assert ("registry", "0002_inventory_and_history") in loader.disk_migrations
for template in (package / "templates" / "registry").glob("*.html"):
    get_template("registry/" + template.name)
assert "CCI Grid Registry" in get_template("registry/base.html").render({})
for asset in (package / "static" / "cci_grids").rglob("*"):
    if asset.is_file():
        assert finders.find("cci_grids/" + str(asset.relative_to(package / "static/cci_grids")))
assert "reset_local_registry" not in get_commands()
assert "describe_grid_fields" not in get_commands()
print("Installed wheel: user model, migration graph, templates and static discovery passed.")
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    wheel = parser.parse_args().wheel.resolve()
    with ZipFile(wheel) as archive:
        names = archive.namelist()
        assert all(name.startswith(("cci_grids/", "cci_grids-")) for name in names)
        assert "cci_grids/migrations/0002_inventory_and_history.py" in names
        assert "cci_grids/templates/registry/base.html" in names
        assert "cci_grids/static/cci_grids/grid-boxes/unclip-4.svg" in names
    with tempfile.TemporaryDirectory(prefix="cci-grids-wheel-") as directory:
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
        # Python's -c search path starts at this temporary installation, not the repo.
        subprocess.run([sys.executable, "-c", PROBE], cwd=directory, check=True)


if __name__ == "__main__":
    main()
