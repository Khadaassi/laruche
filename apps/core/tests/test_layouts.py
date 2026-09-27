from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase


class LayoutTests(SimpleTestCase):
    """Les deux familles de gabarits se compilent et gardent leur structure."""

    def render(self, template):
        request = RequestFactory().get("/")
        return render_to_string(template, request=request)

    def test_parent_mobile_has_bottom_nav(self):
        html = self.render("layouts/parent_mobile.html")
        self.assertIn("fixed inset-x-0 bottom-0", html)
        self.assertIn('lang="fr"', html)

    def test_shared_display_has_top_nav_and_columns(self):
        html = self.render("layouts/shared_display.html")
        self.assertIn("grid-flow-col", html)
        self.assertNotIn("bottom-0", html)

    def test_csrf_token_passed_to_htmx(self):
        html = self.render("layouts/parent_mobile.html")
        self.assertIn('hx-headers=\'{"X-CSRFToken": "', html)

    def test_scripts_are_self_hosted(self):
        html = self.render("base.html")
        self.assertIn("vendor/htmx.min.js", html)
        self.assertIn("vendor/alpine-csp.min.js", html)
        self.assertNotIn("unpkg", html)
        self.assertNotIn("jsdelivr", html)
