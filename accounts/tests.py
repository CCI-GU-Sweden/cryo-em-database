"""Exercise authentication and access boundaries against PostgreSQL."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class AuthenticationTests(TestCase):
    def test_dashboard_roles_control_access_and_revocation(self):
        for role, expected in [("", 403), ("researcher", 403), ("staff", 200), ("admin", 200)]:
            with self.subTest(role=role):
                self.member.role = role
                self.member.save(update_fields=["role"])
                self.client.force_login(self.member)
                self.assertEqual(self.client.get("/").status_code, expected)

    @classmethod
    def setUpTestData(cls):
        # Fictional credentials exist only in Django's temporary test database.
        cls.member = User.objects.create_user(
            username="demo-member", password="test-only-password", role="staff"
        )
        cls.outsider = User.objects.create_user(
            username="demo-outsider", password="test-only-password"
        )

    def test_anonymous_visitor_must_log_in(self):
        self.assertRedirects(self.client.get("/"), "/accounts/login/?next=/")

    def test_member_can_log_in_and_view_home(self):
        response = self.client.post(
            reverse("login"), {"username": "demo-member", "password": "test-only-password"}
        )
        self.assertRedirects(response, reverse("home"))
        self.assertContains(self.client.get("/"), "Welcome, demo-member")

    def test_invalid_password_does_not_authenticate(self):
        response = self.client.post(
            reverse("login"), {"username": "demo-member", "password": "incorrect"}
        )
        self.assertContains(response, "Please enter a correct username and password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_non_member_has_no_registry_access(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get("/").status_code, 403)

    def test_cci_membership_does_not_grant_admin_access(self):
        self.client.force_login(self.member)
        self.assertRedirects(self.client.get("/admin/"), "/admin/login/?next=/admin/")

    def test_administrator_can_view_home(self):
        admin = User.objects.create_superuser(username="demo-admin", password="test-only-password")
        self.client.force_login(admin)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_deactivated_user_loses_existing_session_access(self):
        self.client.force_login(self.member)
        self.member.is_active = False
        self.member.save(update_fields=["is_active"])
        self.assertRedirects(self.client.get("/"), "/accounts/login/?next=/")

    def test_admin_cannot_delete_accounts(self):
        admin = User.objects.create_superuser(username="demo-admin", password="test-only-password")
        self.client.force_login(admin)
        response = self.client.post(
            reverse("admin:accounts_user_delete", args=[self.member.pk]), {"post": "yes"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())

    def test_logout_requires_post_and_clears_session(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_and_logout_require_csrf_tokens(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("login"), {}).status_code, 403)
        client.force_login(self.member)
        self.assertEqual(client.post(reverse("logout")).status_code, 403)

    def test_login_rejects_external_redirect(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "demo-member",
                "password": "test-only-password",
                "next": "https://example.org",
            },
        )
        self.assertRedirects(response, reverse("home"))
