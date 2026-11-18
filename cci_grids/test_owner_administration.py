"""Owner administration does not require the host's Django admin application."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import AuditEvent, OwnerAccessGrant, SampleOwner

User = get_user_model()


class OwnerAdministrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.administrator = User.objects.create_user(username="owner-admin", role="admin")
        cls.staff = User.objects.create_user(username="owner-staff", role="staff")
        cls.researcher = User.objects.create_user(username="owner-researcher", role="researcher")
        cls.owner = SampleOwner.objects.create(name="Synthetic Owner", code="syow")
        cls.grant = OwnerAccessGrant.objects.create(
            owner=cls.owner, user=cls.researcher, role="viewer"
        )

    def test_role_admin_without_django_staff_flag_can_edit_and_audit_owner(self):
        self.assertFalse(self.administrator.is_staff)
        self.assertFalse(self.administrator.is_superuser)
        self.client.force_login(self.administrator)
        url = reverse("registry:owner_edit", args=[self.owner.pk])
        self.assertContains(self.client.get(reverse("registry:owner_list")), url)
        self.assertContains(self.client.get(url), "syow")
        response = self.client.post(
            url,
            {
                "name": "Corrected Owner",
                "affiliation": "Synthetic Lab",
                "notes": "Spelling correction",
                # Identifiers and unrelated properties remain outside this form.
                "code": "evil",
                "owner_code_preview": "evil",
            },
        )
        self.assertRedirects(response, reverse("registry:owner_list"))
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.name, "Corrected Owner")
        self.assertEqual(self.owner.code, "syow")
        self.assertFalse(self.owner.active)
        event = AuditEvent.objects.get(actor=self.administrator)
        self.assertEqual(event.operation, "update")
        self.assertEqual(event.changes["name"]["after"], "Corrected Owner")

    def test_staff_and_researcher_cannot_view_or_post_owner_or_grant_management(self):
        urls = [
            reverse("registry:owner_edit", args=[self.owner.pk]),
            reverse("registry:owner_grants", args=[self.owner.pk]),
            reverse("registry:owner_grant_edit", args=[self.grant.pk]),
        ]
        for actor in [self.staff, self.researcher]:
            self.client.force_login(actor)
            for url in urls:
                with self.subTest(actor=actor.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(
                        self.client.post(
                            url, {"name": "Unauthorized", "role": "editor"}
                        ).status_code,
                        403,
                    )
        self.owner.refresh_from_db()
        self.grant.refresh_from_db()
        self.assertEqual(self.owner.name, "Synthetic Owner")
        self.assertEqual(self.grant.role, "viewer")
        self.assertFalse(AuditEvent.objects.exists())

    def test_admin_can_create_and_edit_grant_but_duplicate_is_rejected(self):
        self.client.force_login(self.administrator)
        url = reverse("registry:owner_grants", args=[self.owner.pk])
        response = self.client.post(url, {"user": self.staff.pk, "role": "operator"})
        self.assertRedirects(response, url)
        grant = OwnerAccessGrant.objects.get(owner=self.owner, user=self.staff)
        self.assertEqual(grant.role, "operator")
        response = self.client.post(url, {"user": self.staff.pk, "role": "editor"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(OwnerAccessGrant.objects.filter(owner=self.owner).count(), 2)
        response = self.client.post(
            reverse("registry:owner_grant_edit", args=[grant.pk]),
            {"user": self.staff.pk, "role": "editor", "owner": "999999"},
        )
        self.assertRedirects(response, url)
        grant.refresh_from_db()
        self.assertEqual(grant.role, "editor")
        self.assertEqual(grant.owner_id, self.owner.pk)
        self.assertEqual(AuditEvent.objects.filter(actor=self.administrator).count(), 2)

    def test_admin_role_revocation_and_csrf_are_enforced(self):
        self.client.force_login(self.administrator)
        url = reverse("registry:owner_edit", args=[self.owner.pk])
        User.objects.filter(pk=self.administrator.pk).update(role="staff")
        self.assertEqual(self.client.post(url, {"name": "Unauthorized"}).status_code, 403)
        User.objects.filter(pk=self.administrator.pk).update(role="admin")
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.administrator)
        self.assertEqual(csrf_client.post(url, {"name": "No CSRF"}).status_code, 403)

    def test_invalid_owner_remains_unchanged_and_unsupported_methods_rejected(self):
        self.client.force_login(self.administrator)
        url = reverse("registry:owner_edit", args=[self.owner.pk])
        self.assertEqual(self.client.post(url, {"name": ""}).status_code, 200)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.name, "Synthetic Owner")
        self.assertFalse(AuditEvent.objects.exists())
        self.assertEqual(self.client.delete(url).status_code, 405)
