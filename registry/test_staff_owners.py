"""Staff registration creates owners without accounts or redundant access grants."""

from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AuditEvent, OwnerAccessGrant, SampleOwner
from .services import (
    create_preparation_session,
    create_sample_owner,
    save_administration_record,
    update_grid_preparation,
)

User = get_user_model()


class StaffOwnerRegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username="synthetic-operator", is_cci_staff=True)
        cls.other_staff = User.objects.create_user(
            username="synthetic-colleague", is_cci_staff=True
        )
        cls.outsider = User.objects.create_user(username="synthetic-outsider", is_staff=True)
        cls.existing_owner = SampleOwner.objects.create(name="Existing Owner", code="exow")

    def test_staff_can_create_owner_without_admin_access_and_continue_to_grids(self):
        self.client.force_login(self.staff)
        url = reverse("registry:new_owner")
        response = self.client.get(reverse("registry:new_session"))
        self.assertContains(response, url)
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"name": "New Synthetic Owner", "action": "generate"})
        self.assertContains(response, "neow")
        self.assertEqual(SampleOwner.objects.count(), 1)
        response = self.client.post(
            url,
            {
                "name": "New Synthetic Owner",
                "affiliation": "Synthetic lab",
                "notes": "Test only",
                "action": "save",
                "owner_code_preview": "neow",
                # These extra fields must never grant someone else rights or edit an existing owner.
                "id": self.existing_owner.pk,
                "user": self.other_staff.pk,
                "role": "viewer",
            },
        )
        owner = SampleOwner.objects.get(code="neow")
        self.assertRedirects(response, reverse("registry:new_session") + f"?owner={owner.pk}")
        self.assertFalse(OwnerAccessGrant.objects.filter(owner=owner).exists())
        self.assertFalse(OwnerAccessGrant.objects.filter(user=self.other_staff).exists())
        self.assertFalse(OwnerAccessGrant.objects.filter(owner=self.existing_owner).exists())
        self.assertEqual(SampleOwner.objects.get(pk=self.existing_owner.pk).name, "Existing Owner")
        session = create_preparation_session(
            actor=self.staff,
            owner=owner,
            prepared_at=timezone.now(),
            grid_count=1,
            preparation={},
            request_token=uuid4(),
        )
        self.assertEqual(session.grids.count(), 1)
        self.assertFalse(self.staff.is_staff)
        self.assertEqual(User.objects.count(), 3)  # Registering an owner creates no login.

    def test_all_staff_see_all_owners_in_directory_and_session_selector(self):
        colleague_owner = create_sample_owner(actor=self.other_staff, name="Colleague Owner")
        inactive = SampleOwner.objects.create(name="Inactive Owner", code="inow", active=False)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("registry:owner_list"))
        self.assertContains(response, self.existing_owner.name)
        self.assertContains(response, colleague_owner.name)
        self.assertContains(response, inactive.name)
        response = self.client.get(reverse("registry:owner_list"), {"q": "colleague"})
        self.assertContains(response, colleague_owner.name)
        self.assertNotContains(response, self.existing_owner.name)
        response = self.client.get(reverse("registry:new_session"))
        choices = set(
            response.context["form"].fields["owner"].queryset.values_list("pk", flat=True)
        )
        self.assertEqual(choices, {self.existing_owner.pk, colleague_owner.pk})
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("registry:owner_list")).status_code, 403)

    def test_staff_can_register_and_edit_each_others_grids_without_grants(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("registry:new_session"),
            {
                "owner": self.existing_owner.pk,
                "prepared_at": "2026-11-04T10:00",
                "grid_count": 1,
                "request_token": uuid4(),
                "sample_description": "Synthetic sample",
            },
        )
        self.assertEqual(response.status_code, 302)
        grid = self.existing_owner.preparationsession_set.get().grids.get()
        self.assertFalse(OwnerAccessGrant.objects.filter(owner=self.existing_owner).exists())
        detail = reverse("registry:grid_detail", args=[grid.pk])
        self.assertContains(self.client.get(detail), "Save this grid")
        update_grid_preparation(
            actor=self.staff,
            grid_id=grid.pk,
            expected_version=1,
            preparation={"sample_description": "Updated synthetic sample"},
        )
        update_grid_preparation(
            actor=self.other_staff,
            grid_id=grid.pk,
            expected_version=2,
            preparation={"sample_description": "Colleague correction"},
        )
        event = AuditEvent.objects.filter(entity_type="Grid", operation="update").first()
        self.assertEqual(event.actor, self.other_staff)
        self.assertEqual(event.changes["sample_description"]["after"], "Colleague correction")

    def test_owner_creation_is_audited_without_automatic_grants(self):
        owner = create_sample_owner(actor=self.staff, name="Synthetic Owner")
        event = AuditEvent.objects.get(entity_type="SampleOwner", entity_id=str(owner.pk))
        self.assertEqual(event.actor, self.staff)
        self.assertFalse(OwnerAccessGrant.objects.exists())

    def test_inactive_non_cci_and_anonymous_accounts_cannot_create_owners(self):
        url = reverse("registry:new_owner")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(
            self.client.post(url, {"name": "Denied", "action": "save"}).status_code, 302
        )
        with self.assertRaises(PermissionDenied):
            create_sample_owner(actor=self.outsider, name="Denied")
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(url, {"name": "Denied", "action": "save"}).status_code, 403
        )
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            create_sample_owner(actor=self.staff, name="Denied")
        self.assertEqual(SampleOwner.objects.count(), 1)

    def test_staff_cannot_manage_existing_owners_or_other_grants(self):
        self.existing_owner.name = "Tampered"
        with self.assertRaises(PermissionDenied):
            save_administration_record(actor=self.staff, instance=self.existing_owner)
        with self.assertRaises(PermissionDenied):
            save_administration_record(
                actor=self.staff,
                instance=OwnerAccessGrant(
                    user=self.staff, owner=self.existing_owner, role="editor"
                ),
            )
        self.existing_owner.refresh_from_db()
        self.assertEqual(self.existing_owner.name, "Existing Owner")
        self.assertFalse(OwnerAccessGrant.objects.exists())

    def test_audit_failure_rolls_back_owner(self):
        with patch(
            "registry.services.record_audit",
            side_effect=RuntimeError("Test failure"),
        ):
            with self.assertRaises(RuntimeError):
                create_sample_owner(actor=self.staff, name="Rollback Owner")
        self.assertEqual(SampleOwner.objects.count(), 1)
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(OwnerAccessGrant.objects.exists())

    def test_owner_registration_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        response = client.post(reverse("registry:new_owner"), {"name": "Denied", "action": "save"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SampleOwner.objects.count(), 1)
