from django.db import migrations


def seed(apps, schema_editor):
    db = schema_editor.connection.alias
    dewar = apps.get_model("registry", "Dewar").objects.using(db).create(name="Dewar 1")
    cane = apps.get_model("registry", "Cane").objects.using(db).create(dewar=dewar, name="Cane 1")
    for color in ["black", "dark_blue", "gold", "green", "light_blue", "purple", "red", "silver"]:
        apps.get_model("registry", "Puck").objects.using(db).create(cane=cane, color=color)
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
            code=code, name=name, svg="grid-boxes/" + svg, layout=layout
        )


class Migration(migrations.Migration):
    dependencies = [("registry", "0014_dewar_gridboxtype_cane_gridbox_gridslot_puck_and_more")]
    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
        migrations.RunSQL(
            """
        CREATE FUNCTION registry_protect_box_event() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Box history cannot be changed or deleted'; END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER protect_box_event BEFORE UPDATE OR DELETE ON registry_boxevent
        FOR EACH ROW EXECUTE FUNCTION registry_protect_box_event();
        """,
            """DROP TRIGGER protect_box_event ON registry_boxevent;
        DROP FUNCTION registry_protect_box_event();""",
        ),
    ]
