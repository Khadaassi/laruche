from django.test import TestCase
from django.urls import reverse


class HealthzTests(TestCase):
    def test_returns_ok(self):
        response = self.client.get(reverse("core:healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_rejects_post(self):
        response = self.client.post(reverse("core:healthz"), secure=True)
        self.assertEqual(response.status_code, 405)

    def test_not_redirected_to_https(self):
        # Exemptée de SECURE_SSL_REDIRECT pour les sondes internes en HTTP.
        response = self.client.get(reverse("core:healthz"), secure=False)
        self.assertEqual(response.status_code, 200)
