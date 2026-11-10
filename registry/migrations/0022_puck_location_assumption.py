from django.db import migrations


def infer(apps, schema_editor):
    Puck = apps.get_model("registry", "Puck")
    Slot = apps.get_model("registry", "GridSlot")
    db = schema_editor.connection.alias
    for puck in Puck.objects.using(db).all():
        occupied = Slot.objects.using(db).filter(box__puck=puck, grid__isnull=False).exists()
        Puck.objects.using(db).filter(pk=puck.pk).update(in_dewar=occupied)


class Migration(migrations.Migration):
    dependencies = [("registry", "0021_puck_in_dewar_puck_version_puckevent")]
    operations = [
        migrations.RunPython(infer, migrations.RunPython.noop),
        migrations.RunSQL(
            """CREATE TRIGGER protect_puck_events BEFORE UPDATE OR DELETE ON registry_puckevent
        FOR EACH ROW EXECUTE FUNCTION registry_protect_box_event();""",
            "DROP TRIGGER protect_puck_events ON registry_puckevent;",
        ),
    ]
