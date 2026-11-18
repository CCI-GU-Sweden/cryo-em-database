"""Contract checks loaded outside this checkout by check_dashboard_integration.py."""

import importlib
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from allauth.socialaccount.models import SocialAccount
from dashboard.modules import registered_modules
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command, get_commands
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, clear_url_caches, reverse
from django.utils import timezone

from cci_grids.grid_storage import place_grid, record_grid_outcome
from cci_grids.models import AuditEvent, Grid, PreparationSession, SampleOwner
from cci_grids.permissions import current_staff
from cci_grids.services import archive_grid, create_preparation_session, create_sample_owner
from cci_grids.storage import change_box, correct_last_box_action, register_box
from cci_grids.storage_models import Cane, Dewar, GridBoxType, Puck

User = get_user_model()


class DashboardContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username="contract-staff", role="staff")
        # Dashboard Admin deliberately need not be a Django admin-site user/superuser.
        cls.admin = User.objects.create_user(username="contract-admin", role="admin")
        cls.researcher = User.objects.create_user(username="contract-researcher", role="researcher")
        cls.pending = User.objects.create_user(username="contract-pending", role="")
        cls.inactive = User.objects.create_user(
            username="contract-disabled", role="staff", is_active=False
        )
        cls.identity = SocialAccount.objects.create(
            user=cls.staff, provider="orcid", uid="0000-0000-0000-0000"
        )
        cls.owner = create_sample_owner(actor=cls.staff, name="Synthetic Contract Owner")
        cls.session = create_preparation_session(
            actor=cls.staff,
            owner=cls.owner,
            prepared_at=timezone.now(),
            grid_count=1,
            preparation={},
            request_token=uuid4(),
        )
        cls.grid = cls.session.grids.get()

    def test_installed_package_uses_dashboard_accounts_and_attribution(self):
        import accounts
        import cci_grids

        self.assertTrue(
            Path(accounts.__file__)
            .resolve()
            .is_relative_to(Path(os.environ["CCI_CONTRACT_DASHBOARD"]))
        )
        self.assertTrue(
            Path(cci_grids.__file__)
            .resolve()
            .is_relative_to(Path(os.environ["CCI_CONTRACT_INSTALLATION"]))
        )
        self.assertIs(PreparationSession._meta.get_field("prepared_by").related_model, User)
        self.assertEqual(self.session.prepared_by, self.identity.user)
        self.assertEqual(AuditEvent.objects.filter(actor=self.staff).count(), 3)
        self.assertFalse(self.admin.is_staff)
        self.assertFalse(self.admin.is_superuser)
        self.assertNotIn("reset_local_registry", get_commands())
        self.assertEqual(connection.vendor, "postgresql")

    def test_fresh_migrations_seed_inventory_and_protect_history(self):
        self.assertEqual(list(Dewar.objects.values_list("name", flat=True)), ["Dewar 1"])
        self.assertEqual(list(Cane.objects.values_list("name", flat=True)), ["Cane 1"])
        self.assertEqual(Puck.objects.count(), 8)
        self.assertFalse(Puck.objects.exclude(in_dewar=False).exists())
        self.assertEqual(GridBoxType.objects.count(), 4)
        self.assertTrue(
            all(
                svg.startswith("cci_grids/")
                for svg in GridBoxType.objects.values_list("svg", flat=True)
            )
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            Grid.objects.filter(pk=self.grid.pk).update(grid_number="forbidden-rewrite")
        event = AuditEvent.objects.filter(actor=self.staff).first()
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditEvent.objects.filter(pk=event.pk).delete()

    def test_staff_and_admin_enter_from_dashboard_and_export(self):
        urls = [
            "registry:grid_list",
            "registry:session_list",
            "registry:owner_list",
            "registry:inventory",
            "registry:puck_inventory",
            "registry:new_owner",
            "registry:new_session",
            "registry:excel_export",
            "registry:session_excel_export",
            "registry:owner_excel_export",
        ]
        self.assertEqual(reverse("registry:grid_list"), "/registry/")
        for user in (self.staff, self.admin):
            self.client.force_login(user)
            with self.subTest(role=user.role):
                home = self.client.get(reverse("home"))
                self.assertContains(home, reverse("registry:grid_list"))
                for name in urls:
                    self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
                detail = self.client.get(reverse("registry:grid_detail", args=[self.grid.pk]))
                self.assertContains(detail, "Centre for Cellular Imaging | Data dashboard")
                overview = self.client.get("/api/modules/cci-grids/overview")
                self.assertEqual(overview.status_code, 200)
                self.assertEqual(overview.json()["module"], "cci-grids")
                self.assertTrue(overview.json()["metrics"])

    def test_unapproved_users_cannot_browse_export_or_mutate(self):
        for user in (self.pending, self.researcher, self.inactive):
            self.client.force_login(user)
            with self.subTest(role=user.role, active=user.is_active):
                for name in (
                    "registry:grid_list",
                    "registry:excel_export",
                    "registry:excel_import",
                ):
                    self.assertIn(self.client.get(reverse(name)).status_code, (302, 403))
                response = self.client.post(
                    reverse("registry:new_owner"), {"name": "Forbidden", "action": "save"}
                )
                self.assertIn(response.status_code, (302, 403))
                self.assertEqual(
                    self.client.get("/api/modules/cci-grids/overview").status_code, 403
                )
                with self.assertRaises(PermissionDenied):
                    create_sample_owner(actor=user, name="Forbidden")
                self.assertNotContains(self.client.get(reverse("home")), 'href="/registry/"')
        self.assertFalse(SampleOwner.objects.filter(name="Forbidden").exists())
        self.client.logout()
        self.assertEqual(self.client.get(reverse("registry:grid_list")).status_code, 302)

    def test_revocation_rejects_stale_service_actor(self):
        User.objects.filter(pk=self.staff.pk).update(role="researcher")
        with self.assertRaises(PermissionDenied):
            current_staff(self.staff)
        with self.assertRaises(PermissionDenied):
            create_sample_owner(actor=self.staff, name="Revoked")

    def test_overview_counts_grids_stored_at_cci_through_physical_actions(self):
        from cci_grids.dashboard_module import overview_metrics

        def assert_count(value, needs_review=0):
            self.assertEqual(
                overview_metrics(self.staff),
                [
                    {"label": "Grids stored at CCI", "value": str(value)},
                    {"label": "Unknown location — needs review", "value": str(needs_review)},
                ],
            )

        assert_count(0, needs_review=1)  # Registration does not establish storage.
        box = register_box(
            actor=self.staff,
            name="Contract stock box",
            box_type_id=GridBoxType.objects.get(code="unclipped4").pk,
            puck_id=Puck.objects.first().pk,
        )
        grid = place_grid(
            actor=self.staff,
            grid_id=self.grid.pk,
            slot_id=box.slots.first().pk,
            clipped=False,
            expected_version=self.grid.version,
            occurred_at=timezone.now(),
        )
        assert_count(1)
        grid = record_grid_outcome(
            actor=self.staff,
            grid_id=grid.pk,
            outcome=Grid.Status.SCREENED_RECOVERED,
            reason="",
            expected_version=grid.version,
        )
        assert_count(1)
        box = change_box(
            actor=self.staff,
            box_id=box.pk,
            expected_version=box.version,
            action="transfer",
            transfer_destination="Synthetic destination lab",
            occurred_at=timezone.now(),
        )
        assert_count(0)
        correct_last_box_action(
            actor=self.staff,
            box_id=box.pk,
            expected_version=box.version,
            event_id=box.events.first().pk,
            approval="approve",
            reason="Synthetic transfer correction",
        )
        assert_count(1)
        grid.refresh_from_db()
        record_grid_outcome(
            actor=self.staff,
            grid_id=grid.pk,
            outcome=Grid.Status.SCREENED_DISCARDED,
            reason="",
            expected_version=grid.version,
        )
        assert_count(0)

    def test_sensitive_action_uses_approval_with_dashboard_identity(self):
        with self.assertRaises(ValidationError):
            archive_grid(
                actor=self.staff,
                grid_id=self.grid.pk,
                approval="password",
                expected_version=self.grid.version,
            )
        archived = archive_grid(
            actor=self.staff,
            grid_id=self.grid.pk,
            approval="approve",
            expected_version=self.grid.version,
        )
        self.assertEqual(archived.deleted_by, self.identity.user)
        from cci_grids.dashboard_module import overview_metrics

        self.assertEqual(
            overview_metrics(self.staff),
            [
                {"label": "Grids stored at CCI", "value": "0"},
                {"label": "Unknown location — needs review", "value": "0"},
            ],
        )

    def test_disabling_registration_removes_routes_card_and_metrics_but_preserves_records(self):
        import dashboard.urls

        self.client.force_login(self.staff)
        self.assertEqual(len(registered_modules()), 1)
        try:
            with override_settings(DASHBOARD_MODULES=[]):
                importlib.reload(dashboard.urls)
                clear_url_caches()
                with self.assertRaises(NoReverseMatch):
                    reverse("registry:grid_list")
                self.assertEqual(self.client.get("/registry/").status_code, 404)
                self.assertEqual(
                    self.client.get("/api/modules/cci-grids/overview").status_code, 404
                )
                self.assertNotContains(self.client.get(reverse("home")), 'href="/registry/"')
                self.assertTrue(Grid.objects.filter(pk=self.grid.pk).exists())
                self.assertEqual(SocialAccount.objects.get(pk=self.identity.pk).user, self.staff)
        finally:
            importlib.reload(dashboard.urls)
            clear_url_caches()
        self.assertEqual(self.client.get(reverse("registry:grid_list")).status_code, 200)

    def test_collectstatic_includes_module_svg_and_dashboard_assets(self):
        with tempfile.TemporaryDirectory(prefix="cci-collected-static-") as directory:
            with override_settings(STATIC_ROOT=directory):
                call_command("collectstatic", interactive=False, verbosity=0)
            root = Path(directory)
            self.assertTrue((root / "cci_grids/app.css").is_file())
            self.assertTrue((root / "cci_grids/grid-boxes/unclip-4.svg").is_file())
            self.assertTrue((root / "js/theme.js").is_file())
        self.assertEqual(settings.TIME_ZONE, "UTC")
