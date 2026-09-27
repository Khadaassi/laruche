from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class SecuritySettingsTests(TestCase):
    """Garde-fous : ces réglages ne doivent jamais régresser."""

    def test_no_wildcard_host(self):
        self.assertNotIn("*", settings.ALLOWED_HOSTS)

    def test_cookies_hardened(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")

    def test_cookies_secure_outside_debug(self):
        # Le runner de tests force DEBUG=False : on vérifie donc la config prod.
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)


class SecurityHeadersTests(TestCase):
    def setUp(self):
        self.response = self.client.get(reverse("core:healthz"), secure=True)

    def test_csp_header(self):
        csp = self.response["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("unsafe-eval", csp)

    def test_frame_and_sniffing_headers(self):
        self.assertEqual(self.response["X-Frame-Options"], "DENY")
        self.assertEqual(self.response["X-Content-Type-Options"], "nosniff")

    def test_hsts_header(self):
        self.assertIn("max-age=31536000", self.response["Strict-Transport-Security"])

    def test_http_redirects_to_https(self):
        response = self.client.get("/nimporte-quoi/", secure=False)
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].startswith("https://"))
