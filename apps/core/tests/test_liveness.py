from unittest import mock

from django.db import connection
from django.test import TestCase, override_settings


class LivezTests(TestCase):
    def test_returns_ok(self):
        response = self.client.get("/livez/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_does_not_touch_database(self):
        # Sinon les sondes toutes les quelques secondes empêchent Neon de s'endormir.
        with mock.patch.object(connection, "cursor", side_effect=AssertionError("DB")):
            response = self.client.get("/livez/", secure=True)
        self.assertEqual(response.status_code, 200)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_not_redirected_to_https(self):
        response = self.client.get("/livez/", secure=False)
        self.assertEqual(response.status_code, 200)

    def test_ignores_unknown_host(self):
        response = self.client.get("/livez/", secure=True, HTTP_HOST="10.0.0.1:10000")
        self.assertEqual(response.status_code, 200)

    def test_rejects_post(self):
        response = self.client.post("/livez/", secure=True)
        self.assertNotEqual(response.status_code, 200)

    def test_other_paths_still_validate_host(self):
        response = self.client.get("/healthz/", secure=True, HTTP_HOST="evil.example")
        self.assertEqual(response.status_code, 400)
