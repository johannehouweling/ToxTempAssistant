from django.test import TestCase
from django.urls import reverse
from toxtempass.models import Person
from toxtempass import utilities


class AdminBetaTests(TestCase):
    def setUp(self):
        # Create a normal person who requested beta
        self.requester = Person.objects.create_user(
            username="requester", email="req@example.com", password="pw"
        )
        utilities.set_beta_requested(self.requester, comment="please admit me")

        # Create an admin user
        self.admin = Person.objects.create_user(
            username="admin", email="admin@example.com", password="pw", is_superuser=True
        )

    def test_admin_can_view_beta_requests(self):
        # Force login as admin
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("admin_beta_user_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Beta signup requests")
        self.assertContains(resp, "req@example.com")

    def test_admin_can_toggle_admit(self):
        self.client.force_login(self.admin)
        # Admit the requester
        resp = self.client.post(
            reverse("toggle_beta_admitted"),
            data={"person_id": str(self.requester.id), "admit": "1"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        # Refresh and check preference
        self.requester.refresh_from_db()
        self.assertTrue(self.requester.preferences.get("beta_admitted"))

        # Revoke admission
        resp2 = self.client.post(
            reverse("toggle_beta_admitted"),
            data={"person_id": str(self.requester.id), "admit": "0"},
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertTrue(data2.get("success"))
        self.requester.refresh_from_db()
        self.assertFalse(self.requester.preferences.get("beta_admitted"))
