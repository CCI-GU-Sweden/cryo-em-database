"""Seed configured inventory and enforce current history protections."""
from django.db import migrations


def seed(apps, schema_editor):
    db = schema_editor.connection.alias
    dewar = apps.get_model("registry", "Dewar").objects.using(db).create(name="Dewar 1")
    cane = apps.get_model("registry", "Cane").objects.using(db).create(dewar=dewar, name="Cane 1")
    for color in ["black", "dark_blue", "gold", "green", "light_blue", "purple", "red", "silver"]:
        apps.get_model("registry", "Puck").objects.using(db).create(cane=cane, color=color, in_dewar=False)
    for code, name, svg, layout in [
        (
            "unclipped4",
            "Unclipped (4)",
            "unclip-4.svg",
            {"unclipped": {"capacity": 4, "clipped": False}},
        ),
        (
            "clipped4",
            "Clipped (4)",
            "clipped-grids-4.svg",
            {"clipped": {"capacity": 4, "clipped": True}},
        ),
        (
            "mixed8",
            "Clipped + unclipped (4 + 4)",
            "clip-unclip-4-4.svg",
            {
                "clipped": {"capacity": 4, "clipped": True},
                "unclipped": {"capacity": 4, "clipped": False},
            },
        ),
        (
            "clipped12",
            "Clipped (12)",
            "clip-12.svg",
            {"clipped": {"capacity": 12, "clipped": True}},
        ),
    ]:
        apps.get_model("registry", "GridBoxType").objects.using(db).create(
            code=code, name=name, svg="cci_grids/grid-boxes/" + svg, layout=layout
        )


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION registry_protect_grid_identity() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Grid records cannot be deleted; preserve their identifiers and history';
    END IF;
    IF NEW.grid_number IS DISTINCT FROM OLD.grid_number
       OR NEW.session_id IS DISTINCT FROM OLD.session_id THEN
        RAISE EXCEPTION 'Grid identifiers and original session cannot be changed';
    END IF;
    IF EXISTS (SELECT 1 FROM registry_deletedgrid WHERE grid_id = OLD.id) THEN
        RAISE EXCEPTION 'Deleted grid records are read-only';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER protect_grid_identity BEFORE UPDATE OR DELETE ON registry_grid
FOR EACH ROW EXECUTE FUNCTION registry_protect_grid_identity();

CREATE FUNCTION registry_protect_session_defaults() RETURNS trigger AS $$
BEGIN
    IF NEW.defaults IS DISTINCT FROM OLD.defaults
       OR NEW.defaults_schema_version IS DISTINCT FROM OLD.defaults_schema_version THEN
        RAISE EXCEPTION 'Original preparation session defaults cannot be changed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER protect_session_defaults BEFORE UPDATE ON registry_preparationsession
FOR EACH ROW EXECUTE FUNCTION registry_protect_session_defaults();

CREATE FUNCTION registry_protect_audit_history() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Audit history cannot be changed or deleted';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER protect_audit_history BEFORE UPDATE OR DELETE ON registry_auditevent
FOR EACH ROW EXECUTE FUNCTION registry_protect_audit_history();

CREATE FUNCTION registry_protect_deletion_archive() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Deletion archive entries cannot be changed or deleted';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER protect_deletion_archive BEFORE UPDATE OR DELETE ON registry_deletedgrid
FOR EACH ROW EXECUTE FUNCTION registry_protect_deletion_archive();


        CREATE FUNCTION registry_protect_box_event() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Box history cannot be changed or deleted'; END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER protect_box_event BEFORE UPDATE OR DELETE ON registry_boxevent
        FOR EACH ROW EXECUTE FUNCTION registry_protect_box_event();


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


    CREATE TRIGGER protect_grid_events BEFORE UPDATE OR DELETE ON registry_gridevent
    FOR EACH ROW EXECUTE FUNCTION registry_protect_box_event();

CREATE TRIGGER protect_puck_events BEFORE UPDATE OR DELETE ON registry_puckevent
        FOR EACH ROW EXECUTE FUNCTION registry_protect_box_event();
"""

REVERSE_SQL = """
DROP TRIGGER protect_puck_events ON registry_puckevent;
DROP TRIGGER protect_grid_events ON registry_gridevent;
DROP TRIGGER guard_box_discard ON registry_gridbox;
DROP FUNCTION registry_guard_box_discard();
DROP TRIGGER protect_box_event ON registry_boxevent;
DROP FUNCTION registry_protect_box_event();
DROP TRIGGER protect_deletion_archive ON registry_deletedgrid;
DROP FUNCTION registry_protect_deletion_archive();
DROP TRIGGER protect_audit_history ON registry_auditevent;
DROP FUNCTION registry_protect_audit_history();
DROP TRIGGER protect_session_defaults ON registry_preparationsession;
DROP FUNCTION registry_protect_session_defaults();
DROP TRIGGER protect_grid_identity ON registry_grid;
DROP FUNCTION registry_protect_grid_identity();
"""


class Migration(migrations.Migration):
    dependencies = [("registry", "0001_initial")]
    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
