"""Canonical wording and non-negative integer blot counts."""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import EditGridForm
from .models import Grid, PreparationSuggestion, SampleOwner
from .services import create_preparation_session, update_grid_preparation
from .suggestions import preparation_suggestions


class PreparationConventionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(
            username="wording-operator", is_cci_staff=True
        )
        cls.owner = SampleOwner.objects.create(name="Synthetic Wording Owner", code="sywo")

    def create(self, **preparation):
        return create_preparation_session(
            actor=self.actor,
            owner=self.owner,
            prepared_at=timezone.now(),
            grid_count=1,
            preparation=preparation,
            request_token=uuid4(),
        ).grids.get()

    def test_casing_is_normalized_on_creation_and_edit_without_changing_other_text(self):
        grid = self.create(
            carbon_description=" No ",
            glow_atmosphere="aIR",
            glow_polarity="nEGATIVE",
            sample_description="Protein ABC",
        )
        self.assertEqual(grid.carbon_description, "no")
        self.assertEqual(grid.glow_atmosphere, "Air")
        self.assertEqual(grid.glow_polarity, "Negative")
        self.assertEqual(grid.sample_description, "Protein ABC")
        self.assertEqual(grid.session.defaults["carbon_description"], "no")
        grid = update_grid_preparation(
            actor=self.actor,
            grid_id=grid.pk,
            expected_version=grid.version,
            preparation={
                "carbon_description": "NO",
                "glow_atmosphere": "mixed gas",
                "glow_polarity": "POSITIVE",
            },
        )
        self.assertEqual(grid.carbon_description, "no")
        self.assertEqual(grid.glow_atmosphere, "Mixed Gas")
        self.assertEqual(grid.glow_polarity, "Positive")

    def test_suggestions_merge_case_variants(self):
        for value in ["No", "NO", "no"]:
            PreparationSuggestion.objects.create(field_name="carbon_description", value=value)
        for value in ["air", "AIR", "Air"]:
            PreparationSuggestion.objects.create(field_name="glow_atmosphere", value=value)
        for value in ["negative", "Negative"]:
            PreparationSuggestion.objects.create(field_name="glow_polarity", value=value)
        choices = preparation_suggestions()
        self.assertEqual(choices["carbon_description"], ["no"])
        self.assertEqual(choices["glow_atmosphere"], ["Air"])
        self.assertEqual(choices["glow_polarity"], ["Negative"])

    def test_multiple_blots_default_zero_or_nonnegative_integer(self):
        self.assertEqual(self.create().multiple_blot, 0)
        for value in [0, 1, 2, 7]:
            self.assertEqual(self.create(multiple_blot=value).multiple_blot, value)
        for invalid in [-1, Decimal("1.5"), "1.5", True, False, "many"]:
            with self.subTest(value=invalid), self.assertRaises(ValidationError):
                self.create(multiple_blot=invalid)
        grid = self.create(multiple_blot=2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Grid.objects.filter(pk=grid.pk).update(multiple_blot=-1)
        grid = update_grid_preparation(
            actor=self.actor,
            grid_id=grid.pk,
            expected_version=grid.version,
            preparation={"multiple_blot": None},
        )
        self.assertEqual(grid.multiple_blot, 0)

    def test_forms_and_registry_expose_only_current_fields(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse("registry:new_session"))
        self.assertContains(response, "Multiple blots")
        self.assertNotContains(response, "Double blot")
        self.assertNotContains(response, "Humidity source wording")
        self.assertNotIn("humidity_raw", EditGridForm.base_fields)
        self.assertNotIn("double_blot", EditGridForm.base_fields)
        self.assertEqual(self.create().session.defaults_schema_version, 4)
        self.assertContains(
            self.client.get(reverse("registry:grid_list")), 'data-column="multiple_blot"'
        )
