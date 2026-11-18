"""Registry forms and dates keep facility meaning in hosts configured for UTC."""

from datetime import datetime
from datetime import timezone as datetime_timezone

from django import forms
from django.http import HttpResponse
from django.template import engines
from django.template.response import TemplateResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone

from .excel_import import _session_values
from .facility_time import FACILITY_TIMEZONE, facility_view
from .models import PreparationSession, SampleOwner


@override_settings(TIME_ZONE="UTC")
class FacilityTimeTests(SimpleTestCase):
    def test_forms_and_delayed_render_use_stockholm_then_restore_host_timezone(self):
        request = RequestFactory().post("/registry/")

        @facility_view
        def view(request):
            parsed = forms.DateTimeField().clean("2026-07-05T13:30")
            self.assertEqual(parsed.utcoffset().total_seconds(), 7200)
            self.assertEqual(timezone.get_current_timezone(), FACILITY_TIMEZONE)
            template = engines["django"].from_string('{{ value|date:"Y-m-d H:i T" }}')
            return TemplateResponse(request, template, {"value": parsed})

        with timezone.override("America/New_York"):
            response = view(request)
            self.assertContains(response, "2026-07-05 13:30 CEST")
            self.assertEqual(timezone.get_current_timezone_name(), "America/New_York")

    def test_session_label_ignores_host_default_timezone(self):
        owner = SampleOwner(pk=1, code="test")
        session = PreparationSession(
            pk=1,
            owner=owner,
            prepared_at=datetime(2026, 11, 3, 23, 30, tzinfo=datetime_timezone.utc),
        )
        self.assertEqual(session.display_name, "Session 1 - test - 261104")

    def test_date_only_import_uses_facility_noon_with_a_utc_host(self):
        warnings = set()
        values = _session_values(
            {"prepared_at": "2026-07-05"},
            {"defaults": "{}", "defaults_schema_version": "7"},
            None,
            warnings,
        )
        self.assertEqual(values["prepared_at"].hour, 12)
        self.assertEqual(values["prepared_at"].utcoffset().total_seconds(), 7200)
        self.assertIn("Europe/Stockholm", next(iter(warnings)))

    @override_settings(CCI_GRIDS_DASHBOARD=True)
    def test_dashboard_layout_is_an_explicit_host_choice(self):
        request = RequestFactory().get("/registry/")
        response = facility_view(lambda request: HttpResponse())(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.cci_grids_base_template, "base.html")

    @override_settings(CCI_GRIDS_DASHBOARD=False)
    def test_default_layout_does_not_require_dashboard_templates(self):
        request = RequestFactory().get("/registry/")
        facility_view(lambda request: HttpResponse())(request)
        self.assertEqual(request.cci_grids_base_template, "registry/standalone_base.html")
