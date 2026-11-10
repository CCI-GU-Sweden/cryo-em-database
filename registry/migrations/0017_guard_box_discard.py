from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("registry", "0016_boxevent_destination_boxevent_occurred_at_and_more")]
    operations = [
        migrations.RunSQL(
            """
    CREATE FUNCTION registry_guard_box_discard() RETURNS trigger AS $$
    BEGIN
      IF NEW.discarded AND EXISTS (
        SELECT 1 FROM registry_gridslot WHERE box_id=OLD.id AND grid_id IS NOT NULL
      ) THEN RAISE EXCEPTION 'Remove all grids before discarding this box'; END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER guard_box_discard BEFORE UPDATE ON registry_gridbox
    FOR EACH ROW EXECUTE FUNCTION registry_guard_box_discard();
    """,
            """DROP TRIGGER guard_box_discard ON registry_gridbox;
    DROP FUNCTION registry_guard_box_discard();""",
        )
    ]
