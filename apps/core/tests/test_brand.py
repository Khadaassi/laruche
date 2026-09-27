"""Garde-fous de la marque : le logomark n'existe qu'à un seul endroit."""

from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

# Géométrie exacte du logomark (hexagone + toit + sol).
HEXAGON = "60,14 99.8,37 99.8,83 60,106 20.2,83 20.2,37"
ROOF = "M36 60 L60 38 L84 60"


class LogoTests(SimpleTestCase):
    def test_logo_partial_has_exact_brand_geometry(self):
        html = render_to_string("components/_logo.html")
        self.assertIn(f'points="{HEXAGON}"', html)
        self.assertIn(f'd="{ROOF}"', html)
        self.assertIn('x1="44" y1="78" x2="76" y2="78"', html)
        self.assertIn("fill-honey", html)
        self.assertIn("stroke-ink", html)

    def test_logo_is_never_duplicated_in_templates(self):
        # Toute page doit inclure components/_logo.html plutôt que recopier le SVG.
        templates = Path(settings.BASE_DIR) / "templates"
        copies = [
            str(path.relative_to(templates))
            for path in templates.rglob("*.html")
            if HEXAGON in path.read_text() and path.name != "_logo.html"
        ]
        self.assertEqual(copies, [])

    def test_favicon_matches_logo_and_is_linked(self):
        favicon = (Path(settings.BASE_DIR) / "static" / "favicon.svg").read_text()
        self.assertIn(HEXAGON, favicon)
        self.assertIn(ROOF, favicon)
        html = render_to_string("base.html", request=RequestFactory().get("/"))
        self.assertIn('rel="icon"', html)
        self.assertIn("favicon.svg", html)

    def test_headers_use_the_logo(self):
        for template in ("layouts/public.html", "parent/_header.html"):
            with self.subTest(template=template):
                self.assertIn(
                    HEXAGON, render_to_string(template, request=RequestFactory().get("/"))
                )
