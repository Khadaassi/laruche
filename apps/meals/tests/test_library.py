"""Bibliothèque de recettes : contenu valide, import sans doublon, isolation."""

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.meals.library import CUISINES, LIBRARY, MOROCCAN
from apps.meals.models import Recipe
from apps.meals.services import import_library
from apps.meals.units import Unit

FORBIDDEN = ("porc", "lardon", "jambon", "bacon", "chorizo", "vin ", "alcool", "bière", "rhum")


class LibraryContentTests(TestCase):
    def test_catalogue_is_well_formed(self):
        self.assertGreaterEqual(len(LIBRARY), 40)
        self.assertEqual(len({r.key for r in LIBRARY}), len(LIBRARY))
        for recipe in LIBRARY:
            self.assertIn(recipe.cuisine, CUISINES)
            self.assertTrue(recipe.steps, recipe.name)
            for name, quantity, unit in recipe.ingredients:
                self.assertIn(unit, Unit.values, f"{recipe.name}: {name}")
                if quantity is not None:
                    self.assertGreater(float(quantity), 0)

    def test_every_cuisine_is_well_stocked(self):
        for cuisine in CUISINES:
            self.assertGreaterEqual(sum(r.cuisine == cuisine for r in LIBRARY), 10, cuisine)

    def test_no_pork_no_alcohol(self):
        for recipe in LIBRARY:
            text = " ".join(
                [recipe.name, *[i[0] for i in recipe.ingredients], *recipe.steps]
            ).lower()
            for word in FORBIDDEN:
                self.assertNotIn(word, text, recipe.name)


class ImportTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")

    def test_import_copies_ingredients_and_steps_once(self):
        created = import_library(self.family, ["harira", "harira", "inconnue"])
        self.assertEqual(len(created), 1)
        recipe = created[0]
        self.assertEqual(recipe.prep_minutes, 60)
        self.assertTrue(recipe.ingredients.filter(name="lentilles vertes").exists())
        self.assertIsNone(recipe.ingredients.get(name="sel").quantity)
        self.assertEqual(recipe.steps.count(), 5)
        self.assertEqual(import_library(self.family, ["harira"]), [])

    def test_page_and_add_all_for_a_cuisine(self):
        self.client.force_login(self.parent)
        url = reverse("meals:library")
        self.assertContains(self.get(url), "Harira")
        self.post(f"{url}?cuisine={MOROCCAN}", {"tout": "1"})
        count = Recipe.objects.filter(family=self.family).count()
        self.assertEqual(count, sum(r.cuisine == MOROCCAN for r in LIBRARY))
        self.assertContains(self.get(url, {"cuisine": MOROCCAN}), "Ajoutée")
        self.assertEqual(self.get(url, {"cuisine": "martienne"}).status_code, 404)

    def test_add_one_and_other_family_unaffected(self):
        other = make_family()
        self.client.force_login(self.parent)
        self.post(reverse("meals:library"), {"cle": "lasagnes"})
        self.assertTrue(
            Recipe.objects.filter(family=self.family, name__startswith="Lasagnes").exists()
        )
        self.assertFalse(Recipe.objects.filter(family=other).exists())

    def test_children_cannot_import(self):
        self.client.force_login(self.kid)
        self.post(reverse("meals:library"), {"cle": "harira"})
        self.assertFalse(Recipe.objects.exists())
