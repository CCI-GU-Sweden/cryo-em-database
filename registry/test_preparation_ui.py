"""Scientific input, private suggestion seeding and registry filtering behavior."""

from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from .forms import EditGridForm, NewSessionForm
from .models import AuditEvent, Grid, PreparationSuggestion, SampleOwner
from .services import create_preparation_session, update_grid_preparation
from .suggestions import preparation_suggestions
from .tables import COLUMNS


class PreparationInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(username="synthetic-prep-admin")
        cls.owner = SampleOwner.objects.create(name="Synthetic Owner", code="syow")
        cls.session = create_preparation_session(
            actor=cls.actor,
            owner=cls.owner,
            prepared_at=timezone.now(),
            grid_count=3,
            preparation={
                "sample_description": "Synthetic Alpha",
                "grid_type": "Synthetic type",
                "grid_box_number": "box-7",
                "sample_concentration_value": Decimal("3.12"),
                "sample_concentration_unit": "mg/mL",
                "blot_time_s": Decimal("4"),
                "multiple_blot": 1,
            },
            request_token=uuid4(),
        )
        cls.first, cls.second, cls.third = cls.session.grids.all()
        update_grid_preparation(
            actor=cls.actor,
            grid_id=cls.second.pk,
            expected_version=1,
            preparation={
                "sample_description": "Synthetic Beta",
                "blot_time_s": 6,
                "multiple_blot": 2,
            },
        )
        update_grid_preparation(
            actor=cls.actor,
            grid_id=cls.third.pk,
            expected_version=1,
            preparation={"blot_time_s": None, "multiple_blot": None},
        )

    def setUp(self):
        self.client.force_login(self.actor)

    def test_device_defaults_are_for_new_sessions_and_can_be_corrected(self):
        form = NewSessionForm(actor=self.actor)
        self.assertEqual(form["glow_device"].value(), "Quorum – GloCube+")
        self.assertEqual(form["freezing_device"].value(), "Vitrobot Mark IV")
        self.assertEqual(EditGridForm(instance=self.first)["glow_device"].value(), "")
        labels = {column["key"]: column["label"] for column in COLUMNS}
        self.assertEqual(labels["glow_device"], "Glow discharge device")
        self.assertEqual(labels["freezing_device"], "Freezing device")
        session = create_preparation_session(
            actor=self.actor,
            owner=self.owner,
            prepared_at=timezone.now(),
            grid_count=2,
            preparation={"glow_device": "Quorum – GloCube+", "freezing_device": "Vitrobot Mark IV"},
            request_token=uuid4(),
        )
        first, second = session.grids.all()
        self.assertEqual(session.defaults["glow_device"], "Quorum – GloCube+")
        self.assertEqual(second.freezing_device, "Vitrobot Mark IV")
        update_grid_preparation(
            actor=self.actor,
            grid_id=first.pk,
            expected_version=first.version,
            preparation={"glow_device": "Unknown", "freezing_device": "Another device"},
        )
        first.refresh_from_db()
        self.assertEqual(first.glow_device, "")
        self.assertEqual(first.freezing_device, "Another device")
        self.assertEqual(second.glow_device, "Quorum – GloCube+")
        session.refresh_from_db()
        self.assertEqual(session.defaults["glow_device"], "Quorum – GloCube+")

    def query(self, *rules, **extra):
        data = {"filters-TOTAL_FORMS": len(rules), "filters-INITIAL_FORMS": 0}
        for index, rule in enumerate(rules):
            data.update({f"filters-{index}-{key}": value for key, value in rule.items()})
        data.update(extra)
        return self.client.get(reverse("registry:grid_list"), data)

    def ids(self, response):
        return set(response.context["page"].object_list.values_list("pk", flat=True))

    def test_concentration_has_two_decimals_and_no_trailing_zero_padding(self):
        self.assertEqual(Grid._meta.get_field("sample_concentration_value").decimal_places, 2)
        with self.assertRaises(ValidationError):
            update_grid_preparation(
                actor=self.actor,
                grid_id=self.first.pk,
                expected_version=1,
                preparation={"sample_concentration_value": Decimal("1.2345")},
            )
        grid = update_grid_preparation(
            actor=self.actor,
            grid_id=self.first.pk,
            expected_version=1,
            preparation={"sample_concentration_value": Decimal("3")},
        )
        grid.refresh_from_db()
        self.assertEqual(
            EditGridForm(instance=grid)["sample_concentration_value"].value(), Decimal("3.00")
        )
        self.assertIn('value="3"', str(EditGridForm(instance=grid)["sample_concentration_value"]))
        response = self.client.get(reverse("registry:grid_list"))
        self.assertContains(response, "3.12")
        self.assertNotContains(response, "3.1200")
        self.assertEqual(self.session.defaults["grid_box_number"], "box-7")
        self.assertEqual(self.session.defaults_schema_version, 7)

    def test_all_decimal_measurements_use_two_places_and_registry_preparation_date_omits_time(self):
        from django.db import models

        from .templatetags.registry_display import column_value

        for field in Grid._meta.fields:
            if isinstance(field, models.DecimalField):
                self.assertEqual(field.decimal_places, 2)
                with self.subTest(field=field.name), self.assertRaises(ValidationError):
                    update_grid_preparation(
                        actor=self.actor,
                        grid_id=self.first.pk,
                        expected_version=1,
                        preparation={field.name: Decimal("1.234")},
                    )
        before = self.session.prepared_at
        self.assertEqual(
            column_value(self.first, "prepared_at"), timezone.localtime(before).strftime("%Y-%m-%d")
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.prepared_at, before)
        self.assertIn(":", column_value(self.first, "created_at"))

    def test_suggestions_reuse_saved_values_and_allow_new_values(self):
        PreparationSuggestion.objects.create(field_name="grid_type", value="Seeded synthetic type")
        options = preparation_suggestions()
        self.assertIn("Synthetic type", options["grid_type"])
        self.assertIn("Seeded synthetic type", options["grid_type"])
        self.assertIn("box-7", options["grid_box_number"])
        self.assertEqual(options["blot_time_s"], ["4", "6"])
        response = self.client.get(reverse("registry:new_session"))
        self.assertContains(response, "Batch (Box/LOT-number)")
        self.assertContains(response, "preparation_suggestions.js")
        self.assertContains(response, "Seeded synthetic type")
        update_grid_preparation(
            actor=self.actor,
            grid_id=self.first.pk,
            expected_version=1,
            preparation={"grid_type": "A completely new type"},
        )
        self.assertIn("A completely new type", preparation_suggestions()["grid_type"])
        self.assertTrue(
            PreparationSuggestion.objects.filter(
                field_name="grid_type", value="Synthetic type"
            ).exists()
        )

    def test_text_numeric_and_multiple_filters_match_inclusively(self):
        response = self.query({"property": "sample_description", "contains": "bEtA"})
        self.assertEqual(self.ids(response), {self.second.pk})
        response = self.query({"property": "blot_time_s", "minimum": 4, "maximum": 6})
        self.assertEqual(self.ids(response), {self.first.pk, self.second.pk})
        response = self.query(
            {"property": "sample_description", "contains": "alpha"},
            {"property": "blot_time_s", "maximum": 4},
        )
        self.assertEqual(self.ids(response), {self.first.pk})
        self.assertEqual(
            self.ids(self.query({"property": "blot_time_s", "minimum": 6})), {self.second.pk}
        )
        self.assertEqual(
            self.ids(self.query({"property": "grid_box_number", "contains": "box-7"})),
            {self.first.pk, self.second.pk, self.third.pk},
        )

    def test_multiple_blot_ranges_date_and_session_property_filters(self):
        for count, expected in [(2, self.second.pk), (1, self.first.pk)]:
            self.assertEqual(
                self.ids(
                    self.query(
                        {
                            "property": "multiple_blot",
                            "minimum": count,
                            "maximum": count,
                        }
                    )
                ),
                {expected},
            )
        self.assertEqual(
            self.ids(self.query({"property": "multiple_blot", "minimum": 1})),
            {self.first.pk, self.second.pk},
        )
        today = timezone.localdate(self.session.prepared_at).isoformat()
        response = self.query({"property": "prepared_at", "from_date": today, "to_date": today})
        self.assertEqual(len(self.ids(response)), 3)
        self.assertEqual(
            len(self.ids(self.query({"property": "owner_code", "contains": "SYOW"}))), 3
        )

    def test_invalid_filter_cannot_broaden_results_or_use_arbitrary_lookups(self):
        for rule in [
            {"property": "blot_time_s", "minimum": 7, "maximum": 2},
            {"property": "blot_time_s", "minimum": "not a number"},
            {"property": "session__prepared_by__password", "contains": "anything"},
            {"property": "sample_description"},
        ]:
            response = self.query(rule)
            self.assertFalse(response.context["filters"].is_valid())
            self.assertEqual(self.ids(response), set())

    def test_columns_include_every_preparation_property_and_preferences_do_not_mutate_records(self):
        response = self.client.get(reverse("registry:grid_list"))
        self.assertContains(response, "Choose columns")
        self.assertContains(response, "Show all")
        self.assertContains(response, 'data-column="grid_box_number"')
        self.assertContains(response, 'data-column="glow_current_ma"')
        self.assertContains(response, f"cci-grid-columns-v1-{self.actor.pk}")
        self.assertTrue(any(column["key"] == "sample_concentration_value" for column in COLUMNS))
        self.assertContains(
            self.client.get(reverse("registry:session_detail", args=[self.session.pk])),
            "Choose columns",
        )

    def test_registry_filter_groups_start_collapsed_and_open_when_they_have_errors(self):
        url = reverse("registry:grid_list")
        response = self.client.get(url)
        self.assertContains(
            response,
            '<details class="preparation-group" data-preparation-group id="preparation-filters">',
        )
        self.assertContains(
            response,
            '<details class="preparation-group" data-preparation-group id="storage-filters">',
        )
        self.assertContains(response, "data-expand-groups")
        self.assertContains(response, "data-collapse-groups")

        response = self.client.get(
            url,
            {
                "filters-TOTAL_FORMS": "1",
                "filters-INITIAL_FORMS": "0",
                "filters-0-property": "sample_description",
            },
        )
        self.assertTrue(response.context["preparation_filter_errors"])
        self.assertContains(
            response,
            '<details class="preparation-group" data-preparation-group '
            'id="preparation-filters" open>',
        )

    def test_filter_parameters_survive_pagination(self):
        Grid.objects.bulk_create(
            [
                Grid(
                    session=self.session,
                    grid_number=f"DEMO-PAGE-{i}",
                    sample_description="Pagination synthetic sample",
                )
                for i in range(51)
            ]
        )
        response = self.query({"property": "sample_description", "contains": "Pagination"})
        self.assertTrue(response.context["page"].has_next())
        self.assertContains(response, "filters-0-property=sample_description")
        self.assertContains(response, "page=2")
        self.assertEqual(
            self.query({"property": "sample_description", "contains": "Pagination"}, page=2)
            .context["page"]
            .paginator.count,
            51,
        )


class SuggestionWorkbookTests(TestCase):
    def test_dry_run_seed_repeat_and_ambiguous_values(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-suggestions.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.title = "Sheet1"
            sheet.cell(3, 1, "Grid number")
            sheet.cell(3, 3, "Sample")
            row = (
                [
                    "DEMO-SOURCE",
                    "Synthetic Owner",
                    "Synthetic protein",
                    "2.5 mg/ml",
                    "Synthetic buffer",
                    "Synthetic grid (ref-12)",
                    "No",
                    "Nitrogen, Positive, 7 mA, 8 s",
                    "2.5 µl",
                    "4 °C",
                    1,
                    "3 s",
                    "0 s",
                    0,
                    "No",
                ]
                + [None] * 13
                + ["Synthetic note"]
            )
            sheet.append(row)
            sheet.cell(5, 1, "DEMO-BLANK")
            sheet.cell(6, 1, "DEMO-FORMULA")
            sheet.cell(6, 3, "=1+1")
            book.save(path)
            output = StringIO()
            call_command("seed_preparation_suggestions", str(path), dry_run=True, stdout=output)
            self.assertFalse(PreparationSuggestion.objects.exists())
            self.assertIn("formula not evaluated", output.getvalue())
            call_command("seed_preparation_suggestions", str(path), stdout=StringIO())
            count = PreparationSuggestion.objects.count()
            call_command("seed_preparation_suggestions", str(path), stdout=StringIO())
            self.assertEqual(PreparationSuggestion.objects.count(), count)
            self.assertEqual(AuditEvent.objects.filter(operation="seed_suggestions").count(), 1)
            self.assertEqual(Grid.objects.count(), 0)
            self.assertFalse(
                PreparationSuggestion.objects.filter(field_name="humidity_raw").exists()
            )
            self.assertFalse(
                PreparationSuggestion.objects.filter(field_name="humidity_percent").exists()
            )
            self.assertFalse(
                PreparationSuggestion.objects.filter(
                    field_name="grid_type_reference", value="ref-12"
                ).exists()
            )
            self.assertFalse(
                PreparationSuggestion.objects.filter(field_name="grid_box_number").exists()
            )
            self.assertTrue(
                PreparationSuggestion.objects.filter(field_name="hold_time_s", value="0").exists()
            )
            source = PreparationSuggestion.objects.get(
                field_name="sample_concentration_value"
            ).source
            self.assertEqual(source["raw_value"], "2.5 mg/ml")
            self.assertEqual(source["cell"], "D4")
