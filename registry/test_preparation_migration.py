"""Exercise the approved cleanup on a populated disposable migration database."""

import json

from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class PrototypePreparationMigrationTests(TransactionTestCase):
    old_target = [("registry", "0005_grid_grid_box_number_and_more")]
    new_target = [("registry", "0006_remove_grid_double_blot_remove_grid_humidity_raw_and_more")]

    def test_cleanup_removes_retired_values_and_restores_history_guards(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.old_target)
        self.addCleanup(
            lambda: MigrationExecutor(connection).migrate(executor.loader.graph.leaf_nodes())
        )
        old = executor.loader.project_state(self.old_target).apps
        user = old.get_model("accounts", "User").objects.create(username="migration-operator")
        owner = old.get_model("registry", "SampleOwner").objects.create(
            name="Migration Owner", code="miow"
        )
        defaults = {
            "humidity_raw": "1",
            "double_blot": False,
            "carbon_description": "No",
            "glow_atmosphere": "AIR",
            "glow_polarity": "negative",
        }
        session = old.get_model("registry", "PreparationSession").objects.create(
            owner_id=owner.pk,
            prepared_by_id=user.pk,
            prepared_at=timezone.now(),
            defaults=defaults,
            defaults_schema_version=2,
        )
        grid = old.get_model("registry", "Grid").objects.create(
            session_id=session.pk,
            grid_number="miow-0001",
            humidity_raw="1",
            double_blot=True,
            carbon_description="NO",
            glow_atmosphere="air",
            glow_polarity="NEGATIVE",
        )
        event = old.get_model("registry", "AuditEvent").objects.create(
            actor_id=user.pk,
            entity_type="PreparationSession",
            entity_id=str(session.pk),
            operation="create",
            changes={"defaults": {"before": None, "after": defaults}},
        )
        Suggestion = old.get_model("registry", "PreparationSuggestion")
        for field, value in [
            ("carbon_description", "No"),
            ("carbon_description", "no"),
            ("glow_atmosphere", "AIR"),
            ("glow_atmosphere", "Air"),
            ("humidity_raw", "1"),
            ("double_blot", "False"),
        ]:
            Suggestion.objects.create(field_name=field, value=value)

        executor = MigrationExecutor(connection)
        executor.migrate(self.new_target)
        current = executor.loader.project_state(self.new_target).apps
        Grid = current.get_model("registry", "Grid")
        Session = current.get_model("registry", "PreparationSession")
        Audit = current.get_model("registry", "AuditEvent")
        Suggestion = current.get_model("registry", "PreparationSuggestion")
        result = Grid.objects.get(pk=grid.pk)
        self.assertEqual(result.grid_number, "miow-0001")
        self.assertEqual(result.version, 2)
        self.assertEqual(result.multiple_blot, 0)
        self.assertEqual(
            (result.carbon_description, result.glow_atmosphere, result.glow_polarity),
            ("no", "Air", "Negative"),
        )
        result = Session.objects.get(pk=session.pk)
        self.assertEqual(result.defaults_schema_version, 3)
        self.assertEqual(result.defaults["multiple_blot"], 0)
        self.assertNotIn("humidity_raw", result.defaults)
        self.assertNotIn("double_blot", result.defaults)
        history = json.dumps(Audit.objects.get(pk=event.pk).changes)
        self.assertNotIn("humidity_raw", history)
        self.assertNotIn("double_blot", history)
        self.assertEqual(
            list(
                Suggestion.objects.filter(field_name="carbon_description").values_list(
                    "value", flat=True
                )
            ),
            ["no"],
        )
        self.assertEqual(
            list(
                Suggestion.objects.filter(field_name="glow_atmosphere").values_list(
                    "value", flat=True
                )
            ),
            ["Air"],
        )
        self.assertFalse(
            Suggestion.objects.filter(field_name__in=["humidity_raw", "double_blot"]).exists()
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            Session.objects.filter(pk=session.pk).update(defaults={})
        with self.assertRaises(DatabaseError), transaction.atomic():
            Audit.objects.filter(pk=event.pk).update(changes={})


class DecimalPrecisionMigrationTests(TransactionTestCase):
    def test_existing_test_measurements_round_to_two_places_and_suggestions_follow(self):
        from decimal import Decimal

        from django.db import models

        old_target = [
            ("registry", "0006_remove_grid_double_blot_remove_grid_humidity_raw_and_more")
        ]
        new_target = [("registry", "0007_alter_grid_blot_force_alter_grid_blot_time_s_and_more")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(old_target)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        old = executor.loader.project_state(old_target).apps
        owner = old.get_model("registry", "SampleOwner").objects.create(
            name="Precision Owner", code="prco"
        )
        session = old.get_model("registry", "PreparationSession").objects.create(
            owner=owner,
            defaults={"sample_concentration_value": "1.235"},
            defaults_schema_version=3,
        )
        Grid = old.get_model("registry", "Grid")
        values = {
            field.name: Decimal("1.235")
            for field in Grid._meta.fields
            if isinstance(field, models.DecimalField)
        }
        values["temperature_c"] = Decimal("-1.235")
        grid = Grid.objects.create(session=session, grid_number="prco-0001", **values)
        Suggestion = old.get_model("registry", "PreparationSuggestion")
        for value in ["1.235", "1.24"]:
            Suggestion.objects.create(field_name="sample_concentration_value", value=value)
        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        current = executor.loader.project_state(new_target).apps
        result = current.get_model("registry", "Grid").objects.get(pk=grid.pk)
        for name in values:
            expected = Decimal("-1.24") if name == "temperature_c" else Decimal("1.24")
            self.assertEqual(getattr(result, name), expected)
        snapshot = current.get_model("registry", "PreparationSession").objects.get(pk=session.pk)
        self.assertEqual(snapshot.defaults["sample_concentration_value"], "1.235")
        self.assertEqual(snapshot.defaults_schema_version, 3)
        self.assertEqual(
            list(
                current.get_model("registry", "PreparationSuggestion")
                .objects.filter(field_name="sample_concentration_value")
                .values_list("value", flat=True)
            ),
            ["1.24"],
        )


class CarbonChoicesMigrationTests(TransactionTestCase):
    def test_unmatched_carbon_becomes_unknown_without_reinterpreting_nm(self):
        old_target = [("registry", "0011_alter_preparationsession_defaults_schema_version")]
        new_target = [("registry", "0012_grid_carbon_thickness_layers_and_more")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(old_target)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        old = executor.loader.project_state(old_target).apps
        owner = old.get_model("registry", "SampleOwner").objects.create(name="Carbon", code="carb")
        session = old.get_model("registry", "PreparationSession").objects.create(
            owner=owner,
            defaults={"carbon_description": "unfamiliar", "carbon_thickness_nm": "4"},
            defaults_schema_version=5,
        )
        Grid = old.get_model("registry", "Grid")
        grid = Grid.objects.create(
            session=session,
            grid_number="carb-0001",
            carbon_description="unfamiliar",
            carbon_thickness_nm=4,
        )
        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        current = executor.loader.project_state(new_target).apps
        result = current.get_model("registry", "Grid").objects.get(pk=grid.pk)
        self.assertEqual(result.carbon_description, "")
        self.assertEqual(result.carbon_thickness_nm, 4)
        self.assertIsNone(result.carbon_thickness_layers)
        saved = current.get_model("registry", "PreparationSession").objects.get(pk=session.pk)
        self.assertEqual(saved.defaults["carbon_description"], "unfamiliar")
        with self.assertRaises(DatabaseError), transaction.atomic():
            current.get_model("registry", "PreparationSession").objects.filter(
                pk=session.pk
            ).update(defaults={})


class DeviceMigrationTests(TransactionTestCase):
    def test_existing_records_keep_unknown_devices_and_original_snapshot(self):
        old_target = [("registry", "0012_grid_carbon_thickness_layers_and_more")]
        new_target = [("registry", "0013_grid_freezing_device_grid_glow_device_and_more")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(old_target)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        old = executor.loader.project_state(old_target).apps
        owner = old.get_model("registry", "SampleOwner").objects.create(name="Device", code="devi")
        session = old.get_model("registry", "PreparationSession").objects.create(
            owner=owner, defaults={"notes": "original"}, defaults_schema_version=6
        )
        grid = old.get_model("registry", "Grid").objects.create(
            session=session, grid_number="devi-0001"
        )
        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        current = executor.loader.project_state(new_target).apps
        result = current.get_model("registry", "Grid").objects.get(pk=grid.pk)
        self.assertEqual(result.glow_device, "")
        self.assertEqual(result.freezing_device, "")
        result = current.get_model("registry", "PreparationSession").objects.get(pk=session.pk)
        self.assertEqual(result.defaults, {"notes": "original"})
        self.assertEqual(result.defaults_schema_version, 6)
