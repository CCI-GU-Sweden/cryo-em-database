"""Registration invariants, direct service permissions and real HTTP workflows."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError, close_old_connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    AuditEvent,
    Grid,
    GridIdentifierCounter,
    OwnerAccessGrant,
    PreparationSession,
    SampleOwner,
)
from .preparation import PREPARATION_FIELDS
from .services import (
    create_preparation_session,
    save_administration_record,
    suggest_owner_code,
    update_grid_preparation,
)

User = get_user_model()


class RegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="demo-admin")
        cls.editor = User.objects.create_user(username="demo-editor", role="staff")
        cls.reader = User.objects.create_user(username="demo-reader", role="staff")
        cls.owner = SampleOwner.objects.create(name="Synthetic Owner", code="syow")
        cls.other_owner = SampleOwner.objects.create(name="Other Owner", code="other")
        OwnerAccessGrant.objects.create(user=cls.editor, owner=cls.owner, role="editor")

    def create_session(self, **overrides):
        arguments = dict(
            actor=self.editor,
            owner=self.owner,
            prepared_at=timezone.now(),
            grid_count=8,
            preparation={
                "sample_description": "Synthetic sample",
                "blot_time_s": Decimal("4"),
                "hold_time_s": Decimal("0"),
                "multiple_blot": 1,
            },
            request_token=uuid.uuid4(),
        )
        arguments.update(overrides)
        return create_preparation_session(**arguments)

    def update_grid(self, grid, **overrides):
        values = {name: getattr(grid, name) for name in PREPARATION_FIELDS}
        values.update(overrides)
        return update_grid_preparation(
            actor=self.editor, grid_id=grid.pk, preparation=values, expected_version=grid.version
        )

    def test_eight_grids_and_two_independent_changes(self):
        session = self.create_session()
        grids = list(session.grids.all())
        self.assertEqual(len(grids), 8)
        self.assertEqual(grids[0].grid_number, "syow-0001")
        for grid in grids[:2]:
            self.update_grid(grid, blot_time_s=Decimal("6"))
        session.refresh_from_db()
        self.assertEqual(session.defaults["blot_time_s"], "4")
        self.assertEqual(session.grids.filter(blot_time_s=6).count(), 2)
        self.assertEqual(session.grids.filter(blot_time_s=4).count(), 6)
        self.assertEqual(session.prepared_by, self.editor)
        self.assertEqual(session.experiment_reference, "")
        audit = AuditEvent.objects.filter(entity_type="Grid", operation="update").first()
        self.assertEqual(audit.actor, self.editor)
        self.assertEqual(audit.changes["blot_time_s"], {"before": "4.00", "after": "6"})

    def test_unknown_zero_and_positive_blot_counts_are_distinct(self):
        grid = self.create_session().grids.first()
        self.assertIsNone(grid.sample_concentration_value)
        self.assertIsNone(grid.humidity_percent)
        self.assertEqual(grid.hold_time_s, 0)
        self.assertEqual(grid.multiple_blot, 1)
        grid = self.create_session(preparation={}).grids.first()
        self.assertIsNone(grid.humidity_percent)
        self.assertEqual(grid.multiple_blot, 0)

    def test_failed_batch_rolls_back_grids_session_audit_and_counter(self):
        original_save = Grid.save

        def fail_second_grid(grid, *args, **kwargs):
            if grid.grid_number == "syow-0002":
                raise ValidationError("Simulated failure partway through a batch.")
            return original_save(grid, *args, **kwargs)

        with patch.object(Grid, "save", fail_second_grid), self.assertRaises(ValidationError):
            self.create_session()
        self.assertEqual(Grid.objects.count(), 0)
        self.assertEqual(PreparationSession.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)
        self.assertFalse(
            GridIdentifierCounter.objects.filter(namespace=f"owner:{self.owner.pk}").exists()
        )
        self.assertEqual(self.create_session().grids.first().grid_number, "syow-0001")

    def test_retry_returns_same_session_without_consuming_identifiers(self):
        token, prepared_at = uuid.uuid4(), timezone.now()
        first = self.create_session(request_token=token, prepared_at=prepared_at)
        second = self.create_session(request_token=token, prepared_at=prepared_at)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Grid.objects.count(), 8)
        self.assertEqual(AuditEvent.objects.filter(entity_type="Grid").count(), 8)
        self.assertEqual(
            GridIdentifierCounter.objects.get(namespace=f"owner:{self.owner.pk}").next_number, 9
        )
        with self.assertRaises(ValidationError):
            self.create_session(request_token=token, prepared_at=prepared_at, grid_count=2)

    def test_direct_service_permissions_and_revocation(self):
        with self.assertRaises(PermissionDenied):
            self.create_session(actor=User())
        # Owner grants do not restrict facility-wide CCI editing.
        grid = self.create_session(actor=self.admin).grids.first()
        for role in ["viewer", "operator"]:
            OwnerAccessGrant.objects.filter(user=self.editor).update(role=role)
            grid = self.update_grid(grid, blot_time_s=Decimal("9"))
        self.editor.is_active = False
        self.editor.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.create_session()
        with self.assertRaises(PermissionDenied):
            self.update_grid(grid, blot_time_s=Decimal("10"))

    def test_validation_rejects_invalid_preparation_and_counts(self):
        for preparation in [
            {"blot_time_s": -1},
            {"humidity_percent": 101},
            {"sample_volume_ul": -1},
            {"sample_concentration_value": 3},
            {"grid_number": "renamed"},
        ]:
            with self.subTest(preparation=preparation), self.assertRaises(ValidationError):
                self.create_session(preparation=preparation)
        for count in [0, -1, 101, True]:
            with self.subTest(count=count), self.assertRaises(ValidationError):
                self.create_session(grid_count=count)
        self.assertEqual(Grid.objects.count(), 0)

    @override_settings(GRID_REGISTRATION_ENABLED=False)
    def test_grid_registration_is_blocked_when_disabled(self):
        with self.assertRaises(ValidationError):
            self.create_session()
        self.assertFalse(Grid.objects.exists())

    def test_stale_edit_cannot_overwrite_a_newer_change(self):
        grid = self.create_session().grids.first()
        self.update_grid(grid, blot_time_s=Decimal("6"))
        with self.assertRaisesMessage(ValidationError, "Reload"):
            self.update_grid(grid, blot_time_s=Decimal("9"))
        grid.refresh_from_db()
        self.assertEqual(grid.blot_time_s, 6)

    def test_partial_service_edit_preserves_other_measurements_and_audit_failure_rolls_back(self):
        grid = self.create_session().grids.first()
        updated = update_grid_preparation(
            actor=self.editor,
            grid_id=grid.pk,
            preparation={"blot_time_s": Decimal("7")},
            expected_version=grid.version,
        )
        self.assertEqual(updated.sample_description, "Synthetic sample")
        self.assertEqual(updated.hold_time_s, 0)
        with patch(
            "cci_grids.services.record_audit", side_effect=RuntimeError("Audit unavailable")
        ):
            with self.assertRaises(RuntimeError):
                update_grid_preparation(
                    actor=self.editor,
                    grid_id=grid.pk,
                    preparation={"blot_time_s": Decimal("9")},
                    expected_version=updated.version,
                )
        grid.refresh_from_db()
        self.assertEqual(grid.blot_time_s, 7)
        self.assertEqual(grid.version, updated.version)

    def test_staff_edits_do_not_require_grants_and_inactive_owner_blocks_creation(
        self,
    ):
        grid = self.create_session(actor=self.admin).grids.first()
        OwnerAccessGrant.objects.filter(user=self.editor).delete()
        self.update_grid(grid, blot_time_s=Decimal("9"))
        self.create_session()  # Registering a new session does not need an owner grant.
        self.owner.active = False
        self.owner.save(update_fields=["active"])
        with self.assertRaises(PermissionDenied):
            self.create_session(actor=self.admin)
        grid.refresh_from_db()
        self.update_grid(grid, blot_time_s=Decimal("10"))

    def test_database_protects_identifiers_snapshots_and_audit_history(self):
        session = self.create_session()
        grid = session.grids.first()
        operations = [
            lambda: Grid.objects.filter(pk=grid.pk).update(grid_number="renamed"),
            lambda: Grid.objects.filter(pk=grid.pk).update(session=self.create_session()),
            lambda: Grid.objects.filter(pk=grid.pk).delete(),
            lambda: PreparationSession.objects.filter(pk=session.pk).update(defaults={}),
            lambda: AuditEvent.objects.update(operation="rewritten"),
            lambda: AuditEvent.objects.all().delete(),
        ]
        for operation in operations:
            with (
                self.subTest(operation=operation),
                self.assertRaises(DatabaseError),
                transaction.atomic(),
            ):
                operation()

    def test_case_insensitive_uniqueness_and_legacy_identifier(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SampleOwner.objects.create(name="Duplicate", code="SYOW")
        grid = self.create_session().grids.first()
        Grid.objects.create(session=grid.session, grid_number="CCI-00001")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Grid.objects.create(session=grid.session, grid_number="SYOW-0001")
        self.assertTrue(Grid.objects.filter(grid_number="CCI-00001").exists())

    def session_post(self, **overrides):
        data = dict(
            owner=self.owner.pk,
            prepared_at="2026-11-03T12:00",
            grid_count=8,
            request_token=str(uuid.uuid4()),
            sample_description="Synthetic sample",
            blot_time_s="4",
            hold_time_s="0",
            multiple_blot="1",
        )
        data.update(overrides)
        return data

    def test_full_form_creation_table_and_individual_edit(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse("registry:new_session"))
        self.assertContains(response, "Sample volume (µL)")
        response = self.client.post(reverse("registry:new_session"), self.session_post())
        session = PreparationSession.objects.get()
        self.assertRedirects(response, reverse("registry:session_detail", args=[session.pk]))
        self.assertContains(self.client.get(response.url), "Original shared settings")
        self.assertContains(self.client.get(reverse("registry:grid_list")), "syow-0001")
        grid = session.grids.first()
        url = reverse("registry:grid_detail", args=[grid.pk])
        self.assertContains(self.client.get(url), "Unclipped")
        data = {
            name: getattr(grid, name)
            for name in PREPARATION_FIELDS
            if getattr(grid, name) is not None
        }
        data.update(
            blot_time_s="6",
            expected_version=grid.version,
            grid_number="malicious-rename",
            session=self.other_owner.pk,
        )
        response = self.client.post(url, data)
        self.assertRedirects(response, url)
        grid.refresh_from_db()
        self.assertEqual(grid.blot_time_s, 6)
        self.assertEqual(grid.grid_number, "syow-0001")
        self.assertEqual(session.grids.filter(blot_time_s=4).count(), 7)
        self.assertContains(self.client.get(url), "Database audit history")
        self.assertContains(
            self.client.get(reverse("registry:grid_list"), {"q": "Synthetic"}), "syow-"
        )

    def test_http_staff_editing_and_non_staff_rejection(self):
        grid = self.create_session().grids.first()
        url = reverse("registry:grid_detail", args=[grid.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.reader)
        self.assertContains(self.client.get(url), "Save this grid")
        # Missing version is still invalid, even though the colleague can edit.
        self.assertEqual(self.client.post(url, {"blot_time_s": 9}).status_code, 200)
        data = {name: getattr(grid, name) for name in PREPARATION_FIELDS}
        data = {name: value if value is not None else "" for name, value in data.items()}
        data.update(expected_version=grid.version, blot_time_s=9)
        self.assertRedirects(self.client.post(url, data), url)
        grid.refresh_from_db()
        self.assertEqual(grid.blot_time_s, 9)
        event = AuditEvent.objects.filter(entity_type="Grid", operation="update").first()
        self.assertEqual(event.actor, self.reader)
        response = self.client.post(reverse("registry:new_session"), self.session_post())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PreparationSession.objects.count(), 2)
        self.assertEqual(self.client.post(url, {"blot_time_s": 9}).status_code, 200)
        outsider = User.objects.create_user(username="outsider")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("registry:grid_list")).status_code, 403)
        self.assertEqual(self.client.post(url, data).status_code, 403)

    def test_invalid_form_and_csrf_do_not_create_records(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("registry:new_session"), self.session_post(blot_time_s=-1)
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Grid.objects.exists())
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.editor)
        self.assertEqual(
            client.post(reverse("registry:new_session"), self.session_post()).status_code, 403
        )

    def test_owner_codes_are_automatic_unique_and_stable_after_renaming(self):
        owners = [
            save_administration_record(
                actor=self.admin, instance=SampleOwner(name="Rafael Silva", code="ignored")
            )
            for _ in range(3)
        ]
        self.assertEqual([owner.code for owner in owners], ["rasi", "rsi1", "rsi2"])
        self.assertEqual(suggest_owner_code("RAFAEL SILVA"), "rsi3")
        owner = owners[0]
        owner.name = "Updated display name"
        owner.code = "attempted-change"
        save_administration_record(actor=self.admin, instance=owner)
        self.assertEqual(owner.code, "rasi")
        owner.active = False
        save_administration_record(actor=self.admin, instance=owner)
        self.assertEqual(suggest_owner_code("Rafael Silva"), "rsi3")

    def test_owner_code_collision_tiers_and_case_insensitive_checks(self):
        from .services import owner_code_candidates

        candidates = list(owner_code_candidates("Rafael Silva"))
        self.assertEqual(candidates[0], "rasi")
        self.assertEqual(candidates[1], "rsi1")
        self.assertEqual(candidates[9], "rsi9")
        self.assertEqual(candidates[10], "rs10")
        self.assertEqual(candidates[99], "rs99")
        self.assertEqual(candidates[100], "r100")
        SampleOwner.objects.bulk_create(
            [
                SampleOwner(name="Synthetic collision", code=code.upper(), active=False)
                for code in candidates[:10]
            ]
        )
        self.assertEqual(suggest_owner_code("Rafael Silva"), "rs10")
        SampleOwner.objects.bulk_create(
            [SampleOwner(name="Synthetic collision", code=code) for code in candidates[10:100]]
        )
        self.assertEqual(suggest_owner_code("Rafael Silva"), "r100")

    def test_available_preview_code_is_preserved_on_save(self):
        code = suggest_owner_code("Rafael Silva")
        owner = save_administration_record(
            actor=self.admin, instance=SampleOwner(name="Rafael Silva"), preferred_code=code
        )
        self.assertEqual(owner.code, code)
        second = save_administration_record(
            actor=self.admin, instance=SampleOwner(name="Rafael Silva"), preferred_code=code
        )
        self.assertEqual(second.code, "rsi1")

    def test_owner_code_handles_long_unicode_and_punctuation_names(self):
        for name in ["Åsa Öberg", "李 明", "!!!", "A" * 100]:
            codes = []
            for _ in range(2):
                owner = save_administration_record(
                    actor=self.admin, instance=SampleOwner(name=name)
                )
                codes.append(owner.code)
                self.assertTrue(owner.code)
                self.assertRegex(owner.code, r"^[a-z0-9]{4}$")
            self.assertNotEqual(*codes)
        self.assertTrue(SampleOwner.objects.filter(code="asob").exists())

    def test_owner_registration_generates_checked_code_before_saving(self):
        self.client.force_login(self.admin)
        url = reverse("registry:new_owner")
        self.assertContains(self.client.get(url), "Create unique code")
        response = self.client.post(url, {"name": "Synthetic", "action": "generate"})
        self.assertContains(response, "synt")
        self.assertEqual(
            SampleOwner.objects.count(), 2
        )  # Generating is a preview, not a draft owner.
        # Simulate another administrator taking the proposed code before confirmation.
        save_administration_record(actor=self.admin, instance=SampleOwner(name="Synthetic"))
        response = self.client.post(
            url,
            {
                "name": "Synthetic",
                "affiliation": "Test lab",
                "notes": "Synthetic only",
                "owner_code_preview": "synt",
                "action": "save",
            },
            follow=True,
        )
        owner = SampleOwner.objects.get(code="snt1")
        self.assertRedirects(response, reverse("registry:new_session") + f"?owner={owner.pk}")
        self.assertContains(response, f'value="{owner.pk}" selected')
        self.assertContains(response, "Sample owner registered with code snt1")
        self.assertFalse(User.objects.filter(username="Synthetic").exists())

    def test_refresh_code_keeps_owner_details(self):
        self.client.force_login(self.admin)
        url = reverse("registry:new_owner")
        response = self.client.post(
            url,
            {
                "name": "Another Name",
                "affiliation": "Retain this lab",
                "notes": "Retain this note",
                "action": "generate",
            },
        )
        self.assertContains(response, "anna")
        self.assertContains(response, "Retain this lab")
        self.assertContains(response, "Retain this note")

    def test_admin_owner_preview_checks_uniqueness_without_registering_owner(self):
        self.client.force_login(self.admin)
        form = self.client.get(reverse("admin:registry_sampleowner_add"))
        self.assertContains(form, 'id="id_owner_code_preview"')
        self.assertContains(form, "readonly")
        self.assertContains(form, "owner_code.js")
        url = reverse("admin:registry_sampleowner_suggest_code")
        response = self.client.get(url, {"name": "Synthetic"})
        self.assertEqual(response.json(), {"code": "synt"})
        self.assertEqual(SampleOwner.objects.count(), 2)
        self.assertEqual(self.client.get(url, {"name": " "}).status_code, 400)
        self.assertEqual(self.client.post(url, {"name": "Synthetic"}).status_code, 405)
        self.reader.is_staff = True
        self.reader.save(update_fields=["is_staff"])
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(url, {"name": "Synthetic"}).status_code, 403)

    def test_admin_owner_grant_management_is_audited_and_science_read_only(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin:registry_sampleowner_add"),
            {"name": "New Synthetic Owner", "code": "NEW", "active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        owner = SampleOwner.objects.get(code="neow")
        self.assertTrue(
            AuditEvent.objects.filter(entity_type="SampleOwner", entity_id=str(owner.pk)).exists()
        )
        response = self.client.post(
            reverse("admin:registry_owneraccessgrant_add"),
            {"user": self.reader.pk, "owner": owner.pk, "role": "editor"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditEvent.objects.filter(entity_type="OwnerAccessGrant").exists())
        self.assertEqual(self.client.post(reverse("admin:registry_grid_add"), {}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            save_administration_record(
                actor=self.editor, instance=SampleOwner(name="Denied", code="deny")
            )


class ConcurrentRegistrationTests(TransactionTestCase):
    def test_simultaneous_owner_registrations_get_distinct_codes(self):
        actor = User.objects.create_superuser(username="concurrent-owner-admin")
        barrier = Barrier(2)

        def register_owner(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return save_administration_record(
                    actor=actor, instance=SampleOwner(name="Same Synthetic Name")
                ).code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            codes = list(executor.map(register_owner, range(2)))
        self.assertEqual(set(codes), {"sana", "sna1"})
        self.assertEqual(AuditEvent.objects.filter(entity_type="SampleOwner").count(), 2)

    def test_simultaneous_batches_have_unique_ids(self):
        actor = User.objects.create_superuser(username="concurrent-demo-admin")
        owner = SampleOwner.objects.create(name="Concurrent synthetic owner", code="cnow")
        barrier = Barrier(2)

        def create_batch(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return create_preparation_session(
                    actor=actor,
                    owner=owner,
                    prepared_at=timezone.now(),
                    grid_count=8,
                    preparation={},
                    request_token=uuid.uuid4(),
                ).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            sessions = list(executor.map(create_batch, range(2)))
        self.assertEqual(len(set(sessions)), 2)
        self.assertEqual(Grid.objects.count(), 16)
        self.assertEqual(len(set(Grid.objects.values_list("grid_number", flat=True))), 16)
