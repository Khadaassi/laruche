"""Appli installable : manifeste, service worker, page hors connexion, en-têtes."""

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin


class PwaTests(SecureClientMixin, TestCase):
    def test_manifest(self):
        response = self.get(reverse("core:manifest"))
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        data = response.json()
        self.assertEqual(data["display"], "standalone")
        self.assertTrue(any(i.get("purpose") == "maskable" for i in data["icons"]))

    def test_service_worker_at_root_never_caches_pages(self):
        response = self.get(reverse("core:service_worker"))
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        body = response.content.decode()
        self.assertIn("/hors-ligne/", body)
        self.assertIn("showNotification", body)

    def test_offline_page_is_public(self):
        self.assertContains(self.get(reverse("core:offline")), "Pas de connexion")

    def test_pages_link_the_manifest_and_csp_allows_it(self):
        response = self.get(reverse("accounts:login"))
        self.assertContains(response, 'rel="manifest"')
        csp = response["Content-Security-Policy"]
        self.assertIn("manifest-src 'self'", csp)
        self.assertIn("worker-src 'self'", csp)
