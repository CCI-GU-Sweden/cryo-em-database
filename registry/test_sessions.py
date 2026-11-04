"""Session labels and facility-wide browsing without changing stored identity."""

from datetime import datetime
from datetime import timezone as datetime_timezone
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AuditEvent, PreparationSession, SampleOwner
from .services import create_preparation_session

User = get_user_model()


class SessionBrowserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user(
            username="synthetic-jens", first_name="Jens", last_name="Synthetic", is_cci_staff=True
        )
        cls.colleague = User.objects.create_user(username="synthetic-colleague", is_cci_staff=True)
        cls.owner = SampleOwner.objects.create(name="Alpha synthetic owner", code="rasi")
        cls.other_owner = SampleOwner.objects.create(name="Beta synthetic owner", code="beow")
        cls.first = create_preparation_session(
            actor=cls.operator,
            owner=cls.owner,
            prepared_at=datetime(2026, 11, 3, 23, 30, tzinfo=datetime_timezone.utc),
            grid_count=2,
            preparation={},
            request_token=uuid4(),
            experiment_reference="EXP-A",
            project_reference="Project-X",
        )
        cls.second = create_preparation_session(
            actor=cls.colleague,
            owner=cls.other_owner,
            prepared_at=datetime(2026, 11, 5, 12, tzinfo=datetime_timezone.utc),
            grid_count=1,
            preparation={},
            request_token=uuid4(),
            experiment_reference="EXP-B",
        )

    def setUp(self):
        self.client.force_login(self.operator)

    def ids(self, response):
        return {session.pk for session in response.context["page"]}

    def test_label_uses_owner_code_and_facility_preparation_date(self):
        expected = f"Session {self.first.pk} - rasi - 261104"
        with timezone.override("UTC"):
            self.assertEqual(self.first.display_name, expected)
        self.assertEqual(str(self.first), expected)
        legacy = PreparationSession.objects.create(owner=self.owner, defaults={})
        self.assertEqual(legacy.display_name, f"Session {legacy.pk} - rasi - undated")

    def test_navigation_lists_all_staff_sessions_with_correct_grid_counts(self):
        url = reverse("registry:session_list")
        self.assertContains(self.client.get(reverse("home")), url)
        response = self.client.get(url)
        self.assertEqual(self.ids(response), {self.first.pk, self.second.pk})
        sessions = {session.pk: session for session in response.context["page"]}
        self.assertEqual(sessions[self.first.pk].grid_count, 2)
        self.assertEqual(sessions[self.second.pk].grid_count, 1)
        self.assertContains(response, self.first.display_name)
        self.assertContains(response, self.second.display_name)
        self.assertContains(response, "Jens Synthetic")

    def test_search_matches_owner_operator_references_and_session_number(self):
        url = reverse("registry:session_list")
        for query in [
            "rasi",
            "Alpha synthetic owner",
            "synthetic-jens",
            "Jens Synthetic",
            "exp-a",
            "project-x",
            f"Session {self.first.pk}",
        ]:
            with self.subTest(query=query):
                self.assertEqual(self.ids(self.client.get(url, {"q": query})), {self.first.pk})
        self.assertEqual(self.ids(self.client.get(url, {"q": "EXP-B"})), {self.second.pk})

    def test_owner_and_date_filters_are_inclusive_and_bad_ranges_fail_closed(self):
        url = reverse("registry:session_list")
        self.assertEqual(self.ids(self.client.get(url, {"owner": self.owner.pk})), {self.first.pk})
        response = self.client.get(url, {"from_date": "2026-11-04", "to_date": "2026-11-04"})
        self.assertEqual(self.ids(response), {self.first.pk})
        response = self.client.get(url, {"from_date": "2026-11-06", "to_date": "2026-11-01"})
        self.assertEqual(self.ids(response), set())
        self.assertContains(response, "The start date must not be after the end date.")
        self.assertEqual(self.ids(self.client.get(url, {"owner": "not-an-owner"})), set())

    def test_session_and_grid_detail_use_the_label_and_keep_full_timestamp(self):
        before = self.first.prepared_at
        history_count = AuditEvent.objects.count()
        response = self.client.get(reverse("registry:session_detail", args=[self.first.pk]))
        self.assertContains(response, self.first.display_name)
        self.assertContains(response, "00:30")
        grid = self.first.grids.first()
        self.assertContains(
            self.client.get(reverse("registry:grid_detail", args=[grid.pk])),
            self.first.display_name,
        )
        self.first.refresh_from_db()
        self.assertEqual(self.first.prepared_at, before)
        self.assertEqual(AuditEvent.objects.count(), history_count)

    def test_browser_requires_active_cci_access(self):
        url = reverse("registry:session_list")
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        outsider = User.objects.create_user(username="session-outsider", is_staff=True)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.operator)
        self.operator.is_active = False
        self.operator.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_pagination_preserves_search_and_owner_filters(self):
        PreparationSession.objects.bulk_create(
            [
                PreparationSession(
                    owner=self.other_owner, experiment_reference="Pagination synthetic"
                )
                for _ in range(51)
            ]
        )
        url = reverse("registry:session_list")
        params = {"q": "Pagination", "owner": self.other_owner.pk}
        response = self.client.get(url, params)
        self.assertEqual(response.context["page"].paginator.count, 51)
        self.assertContains(response, "q=Pagination")
        self.assertContains(response, f"owner={self.other_owner.pk}")
        self.assertContains(response, "page=2")
        response = self.client.get(url, {**params, "page": 2})
        self.assertEqual(len(response.context["page"]), 1)
