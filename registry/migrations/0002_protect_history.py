"""Enforce immutable identifiers and history even for bulk ORM updates.

PostgreSQL triggers complement the service layer: generic admin/QuerySet writes
must not silently rename physical grids or rewrite the original session settings.
"""

from django.db import migrations


FORWARD_SQL = """
CREATE FUNCTION registry_protect_grid_identity() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Grid records cannot be deleted; preserve their identifiers and history';
    END IF;
    IF NEW.grid_number IS DISTINCT FROM OLD.grid_number
       OR NEW.session_id IS DISTINCT FROM OLD.session_id THEN
        RAISE EXCEPTION 'Grid identifiers and original session cannot be changed';
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
"""
REVERSE_SQL = """
DROP TRIGGER protect_audit_history ON registry_auditevent;
DROP FUNCTION registry_protect_audit_history();
DROP TRIGGER protect_session_defaults ON registry_preparationsession;
DROP FUNCTION registry_protect_session_defaults();
DROP TRIGGER protect_grid_identity ON registry_grid;
DROP FUNCTION registry_protect_grid_identity();
"""


def seed_demo_counter(apps, schema_editor):
    apps.get_model("registry", "GridIdentifierCounter").objects.using(
        schema_editor.connection.alias
    ).get_or_create(namespace="DEMO", defaults={"next_number": 1})


class Migration(migrations.Migration):
    dependencies = [("registry", "0001_initial")]
    operations = [
        migrations.RunPython(seed_demo_counter, migrations.RunPython.noop),
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
