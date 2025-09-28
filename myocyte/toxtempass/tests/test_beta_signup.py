from django.test import TestCase
from django.urls import reverse
from toxtempass.models import Person
from toxtempass import utilities
from toxtempass.tasks import send_beta_signup_notification


class BetaSignupTests(TestCase):
    def test_generate_and_verify_token(self):
        p = Person.objects.create_user(username="tester", email="t@example.com", password="pw")
        token = utilities.generate_beta_token(p.id)
        payload = utilities.verify_beta_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(int(payload["person_id"]), p.id)

    def test_set_requested_and_admit_helpers(self):
        p = Person.objects.create_user(username="tester2", email="t2@example.com", password="pw")
        utilities.set_beta_requested(p, comment="please")
        self.assertTrue(p.preferences.get("beta_signup"))
        self.assertFalse(p.preferences.get("beta_admitted", False))

        utilities.set_beta_admitted(p, True, comment="ok")
        p.refresh_from_db()
        self.assertTrue(p.preferences.get("beta_admitted"))
        self.assertIsNotNone(p.preferences.get("beta_admitted_at"))

    def test_send_beta_notification_queues(self):
        p = Person.objects.create_user(username="tester3", email="t3@example.com", password="pw")
        # ensure preferences exist
        utilities.set_beta_requested(p, comment="test")
        task_id = send_beta_signup_notification(p.id)
        self.assertIsNotNone(task_id)
