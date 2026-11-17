"""Move existing configured box SVG references into the package namespace."""

from django.db import migrations


def namespace_assets(apps, schema_editor):
    box_types = apps.get_model("registry", "GridBoxType").objects.using(
        schema_editor.connection.alias
    )
    for kind in box_types.filter(svg__startswith="grid-boxes/"):
        kind.svg = "cci_grids/" + kind.svg
        kind.save(update_fields=["svg"])


class Migration(migrations.Migration):
    dependencies = [("registry", "0002_inventory_and_history")]
    operations = [migrations.RunPython(namespace_assets, migrations.RunPython.noop)]
