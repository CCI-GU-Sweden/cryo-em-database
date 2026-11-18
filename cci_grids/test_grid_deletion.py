"""Password-confirmed record deletion preserves data, history and grid IDs."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import AuditEvent, DeletedGrid, Grid, SampleOwner
from .services import archive_grid, create_preparation_session, update_grid_preparation

User = get_user_model()


class GridDeletionTests(TestCase):
    operator_password = "test-only-operator-password"
    reviewer_password = "test-only-reviewer-password"

    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user(
            username="archive-operator", password=cls.operator_password, role="staff"
        )
        cls.reviewer = User.objects.create_user(
            username="archive-reviewer", password=cls.reviewer_password, role="staff"
        )
        cls.outsider = User.objects.create_user(username="archive-outsider", is_staff=True)
        cls.owner = SampleOwner.objects.create(name="Synthetic Archive Owner", code="syar")
        cls.timestamp, cls.token = timezone.now(), uuid4()
        cls.session = create_preparation_session(
            actor=cls.operator,
            owner=cls.owner,
            prepared_at=cls.timestamp,
            grid_count=3,
            preparation={"sample_description": "Synthetic archive sample", "blot_time_s": 4},
            request_token=cls.token,
        )
        cls.grid = cls.session.grids.first()

    def archive(self, **overrides):
        arguments = dict(
            actor=self.reviewer,
            grid_id=self.grid.pk,
            approval="approve",
            expected_version=self.grid.version,
        )
        arguments.update(overrides)
        return archive_grid(**arguments)

    def confirmation_data(self, **overrides):
        data = {
            "approval": "approve",
            "expected_version": self.grid.version,
        }
        data.update(overrides)
        return data

    def test_any_cci_staff_can_archive_with_their_own_password_and_preserve_record(self):
        record = self.archive()
        self.assertEqual(record.deleted_by, self.reviewer)
        self.assertEqual(record.grid_id, self.grid.pk)
        self.assertEqual(Grid.objects.count(), 3)
        self.assertEqual(Grid.objects.active().count(), 2)
        self.assertEqual(Grid.objects.archived().count(), 1)
        grid = Grid.objects.get(pk=self.grid.pk)
        self.assertEqual(grid.sample_description, "Synthetic archive sample")
        self.assertEqual(grid.blot_time_s, 4)
        self.assertEqual(grid.version, self.grid.version + 1)
        self.assertEqual(grid.session_id, self.session.pk)
        event = AuditEvent.objects.get(
            entity_type="Grid", entity_id=str(grid.pk), operation="archive"
        )
        self.assertEqual(event.actor, self.reviewer)
        self.assertTrue(event.changes["deleted"]["after"])
        self.assertNotIn(self.reviewer_password, json.dumps(event.changes))

    def test_wrong_and_unusable_passwords_do_not_delete(self):
        before = AuditEvent.objects.count()
        for overrides in [
            {"approval": "wrong-password"},
            {"approval": self.operator_password},
            {"approval": ""},
        ]:
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                self.archive(**overrides)
        no_password = User.objects.create_user(username="no-local-password", role="staff")
        with self.assertRaises(ValidationError):
            self.archive(actor=no_password, approval="invalid")
        self.assertEqual(AuditEvent.objects.count(), before)
        self.assertFalse(DeletedGrid.objects.exists())
        self.assertTrue(Grid.objects.active().filter(pk=self.grid.pk).exists())

    def test_non_staff_and_deactivated_accounts_cannot_archive(self):
        with self.assertRaises(PermissionDenied):
            self.archive(actor=self.outsider)
        self.reviewer.is_active = False
        self.reviewer.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.archive()
        self.assertFalse(DeletedGrid.objects.exists())

    def test_stale_confirmation_does_not_remove_a_changed_record(self):
        update_grid_preparation(
            actor=self.operator,
            grid_id=self.grid.pk,
            expected_version=self.grid.version,
            preparation={"sample_description": "Corrected synthetic sample"},
        )
        with self.assertRaisesMessage(ValidationError, "changed"):
            self.archive()
        self.assertFalse(DeletedGrid.objects.exists())
        self.assertTrue(Grid.objects.active().filter(pk=self.grid.pk).exists())

    def test_archive_and_version_roll_back_if_audit_cannot_be_written(self):
        before = AuditEvent.objects.count()
        with patch(
            "cci_grids.services.record_audit", side_effect=RuntimeError("Test audit failure")
        ):
            with self.assertRaises(RuntimeError):
                self.archive()
        self.grid.refresh_from_db()
        self.assertEqual(self.grid.version, 1)
        self.assertFalse(DeletedGrid.objects.exists())
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_retries_are_idempotent_and_never_bypass_password_confirmation(self):
        first = self.archive()
        second = self.archive()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(DeletedGrid.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(operation="archive").count(), 1)
        with self.assertRaises(ValidationError):
            self.archive(approval="wrong-password")

    def test_archived_record_cannot_be_edited_or_unarchived_by_bulk_updates(self):
        self.archive()
        with self.assertRaises(PermissionDenied):
            update_grid_preparation(
                actor=self.operator,
                grid_id=self.grid.pk,
                expected_version=2,
                preparation={"notes": "Denied"},
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            Grid.objects.filter(pk=self.grid.pk).update(notes="Denied")
        with self.assertRaises(DatabaseError), transaction.atomic():
            DeletedGrid.objects.all().delete()
        with self.assertRaises(DatabaseError), transaction.atomic():
            DeletedGrid.objects.all().update(deleted_by=self.operator)

    def test_delete_flow_requires_confirmation_and_never_echoes_password(self):
        self.client.force_login(self.reviewer)
        detail = reverse("registry:grid_detail", args=[self.grid.pk])
        url = reverse("registry:grid_delete", args=[self.grid.pk])
        self.assertContains(self.client.get(detail), 'class="danger-button">Delete</button>')
        confirmation = self.client.get(url)
        self.assertContains(confirmation, 'name="approval"')
        self.assertContains(confirmation, self.grid.grid_number)
        self.assertNotContains(confirmation, 'name="confirmation"')
        self.assertFalse(DeletedGrid.objects.exists())
        response = self.client.post(url, self.confirmation_data(approval="test-secret-not-echoed"))
        self.assertContains(response, "Type approve to confirm")
        self.assertFalse(DeletedGrid.objects.exists())
        self.assertRedirects(
            self.client.post(url, self.confirmation_data()), reverse("registry:grid_list")
        )
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.post(detail, {"notes": "Denied"}).status_code, 404)
        archive_url = reverse("registry:deleted_grid_detail", args=[self.grid.pk])
        self.assertRedirects(self.client.get(url), archive_url)
        response = self.client.get(archive_url)
        self.assertContains(response, "Archived record — read-only")
        self.assertContains(response, "Synthetic archive sample")
        self.assertNotContains(response, "Save this grid")
        self.assertEqual(self.client.post(archive_url, {"notes": "Denied"}).status_code, 405)
        self.assertEqual(Grid.objects.get(pk=self.grid.pk).notes, "")

    def test_registry_session_counts_and_filters_exclude_deleted_grids(self):
        self.archive()
        self.client.force_login(self.reviewer)
        registry = self.client.get(reverse("registry:grid_list"))
        ids = set(registry.context["page"].object_list.values_list("pk", flat=True))
        self.assertNotIn(self.grid.pk, ids)
        registry = self.client.get(reverse("registry:grid_list"), {"q": self.grid.grid_number})
        self.assertEqual(registry.context["page"].paginator.count, 0)
        session = self.client.get(reverse("registry:session_detail", args=[self.session.pk]))
        self.assertEqual(session.context["grids"].count(), 2)
        self.assertEqual(session.context["deleted_count"], 1)
        sessions = self.client.get(reverse("registry:session_list"))
        self.assertEqual(sessions.context["page"][0].grid_count, 2)
        self.assertEqual(sessions.context["page"][0].deleted_count, 1)
        archive = self.client.get(
            reverse("registry:deleted_grid_list"), {"session": self.session.pk}
        )
        self.assertContains(archive, self.grid.grid_number)
        self.assertEqual(archive.context["page"].paginator.count, 1)
        self.assertEqual(
            self.client.get(reverse("registry:deleted_grid_detail", args=[999999])).status_code, 404
        )

    def test_deleted_ids_are_reserved_and_original_batch_retries_do_not_recreate_them(self):
        self.archive()
        repeated = create_preparation_session(
            actor=self.operator,
            owner=self.owner,
            prepared_at=self.timestamp,
            grid_count=3,
            preparation={"sample_description": "Synthetic archive sample", "blot_time_s": 4},
            request_token=self.token,
        )
        self.assertEqual(repeated.pk, self.session.pk)
        self.assertEqual(repeated.grids.count(), 3)
        self.assertEqual(repeated.grids.active().count(), 2)
        later = create_preparation_session(
            actor=self.operator,
            owner=self.owner,
            prepared_at=timezone.now(),
            grid_count=1,
            preparation={},
            request_token=uuid4(),
        )
        self.assertEqual(later.grids.get().grid_number, "syar-0004")

    def test_archive_routes_and_post_actions_require_staff_csrf_and_expected_version(self):
        url = reverse("registry:grid_delete", args=[self.grid.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.outsider)
        for route in [
            url,
            reverse("registry:deleted_grid_list"),
            reverse("registry:deleted_grid_detail", args=[self.grid.pk]),
        ]:
            self.assertEqual(self.client.get(route).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reviewer)
        self.assertEqual(client.post(url, self.confirmation_data()).status_code, 403)
        self.client.force_login(self.reviewer)
        response = self.client.post(url, {"approval": "approve"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DeletedGrid.objects.exists())
        self.assertEqual(self.client.delete(url).status_code, 405)


class ConcurrentGridDeletionTests(TransactionTestCase):
    def test_simultaneous_confirmation_creates_one_archive_entry_and_audit_event(self):
        password = "test-only-concurrent-password"
        user = User.objects.create_user(
            username="concurrent-archiver", password=password, role="staff"
        )
        owner = SampleOwner.objects.create(name="Concurrent archive owner", code="caow")
        grid = create_preparation_session(
            actor=user,
            owner=owner,
            prepared_at=timezone.now(),
            grid_count=1,
            preparation={},
            request_token=uuid4(),
        ).grids.get()
        barrier = Barrier(2)

        def submit(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return archive_grid(
                    actor=user,
                    grid_id=grid.pk,
                    approval="approve",
                    expected_version=grid.version,
                ).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            archives = list(executor.map(submit, range(2)))
        self.assertEqual(len(set(archives)), 1)
        self.assertEqual(DeletedGrid.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(operation="archive").count(), 1)
