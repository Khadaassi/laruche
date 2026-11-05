"""Menu assisté : remplit les repas vides sans jamais écraser, varie les recettes."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.meals.models import Meal, MealKind, MealSlot, Recipe
from apps.meals.suggest import empty_slots, suggest_week

MONDAY = datetime.date(2026, 11, 16)
# Dimanche 15 novembre, 18h : on prépare la semaine du 16.
SUNDAY_6PM = datetime.datetime(2026, 11, 15, 17, 0, tzinfo=datetime.UTC)


@mock.patch("django.utils.timezone.now", return_value=SUNDAY_6PM)
class SuggestTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.recipes = [
            Recipe.objects.create(family=self.family, name=f"Recette {i}", is_favorite=i < 3)
            for i in range(12)
        ]

    def test_targets_dinners_and_free_lunches(self, _now):
        slots = empty_slots(self.family, MONDAY)
        self.assertEqual(len(slots), 7 + 3)
        lunches = [d.weekday() for d, m in slots if m == Meal.LUNCH]
        self.assertEqual(lunches, [2, 5, 6])

    def test_fills_only_empty_slots_without_repeats(self, _now):
        MealSlot.objects.create(
            family=self.family, date=MONDAY, meal=Meal.DINNER, kind=MealKind.LEFTOVERS
        )
        created = suggest_week(self.family, MONDAY)
        self.assertEqual(len(created), 9)
        self.assertEqual(
            MealSlot.objects.get(date=MONDAY, meal=Meal.DINNER).kind, MealKind.LEFTOVERS
        )
        names = [s.recipe.name for s in created]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(suggest_week(self.family, MONDAY), [])  # rien à refaire

    def test_avoids_recently_served_recipes(self, _now):
        last_week = MONDAY - datetime.timedelta(days=3)
        for recipe in self.recipes[:2]:
            MealSlot.objects.create(
                family=self.family,
                date=last_week,
                meal=Meal.DINNER if recipe is self.recipes[0] else Meal.LUNCH,
                kind=MealKind.RECIPE,
                recipe=recipe,
            )
        created = suggest_week(self.family, MONDAY)
        self.assertNotIn(self.recipes[0], [s.recipe for s in created])
        self.assertNotIn(self.recipes[1], [s.recipe for s in created])

    def test_few_recipes_still_fill_the_week(self, _now):
        Recipe.objects.exclude(pk__in=[r.pk for r in self.recipes[:2]]).delete()
        self.assertEqual(len(suggest_week(self.family, MONDAY)), 10)

    def test_other_family_recipes_are_never_used(self, _now):
        other = make_family()
        Recipe.objects.create(family=other, name="Étrangère")
        names = {s.recipe.name for s in suggest_week(self.family, MONDAY)}
        self.assertNotIn("Étrangère", names)

    def test_endpoint(self, _now):
        self.client.force_login(self.parent)
        url = f"{reverse('meals:suggest')}?semaine={MONDAY.isoformat()}"
        response = self.post(url, {"suivant": "revue"})
        self.assertRedirects(
            response,
            f"{reverse('review:week')}?semaine={MONDAY.isoformat()}",
            fetch_redirect_response=False,
        )
        self.assertEqual(MealSlot.objects.filter(family=self.family).count(), 10)
