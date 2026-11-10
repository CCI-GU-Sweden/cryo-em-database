from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("registry", "0019_grid_is_clipped_gridevent")]
    operations = [
        migrations.RunSQL(
            """
    CREATE TRIGGER protect_grid_events BEFORE UPDATE OR DELETE ON registry_gridevent
    FOR EACH ROW EXECUTE FUNCTION registry_protect_box_event();
    """,
            "DROP TRIGGER protect_grid_events ON registry_gridevent;",
        )
    ]
