"""Convives par repas (cantine, absences, saisie) et courses adaptées."""

import datetime
from decimal import Decimal

from django.test import TestCase

from apps.absences.models import Absence, AbsenceKind
from apps.families.tests.factories import join, make_child_profile, make_family
from apps.meals.models import Meal, MealKind, MealSlot, Recipe, RecipeIngredient
from apps.meals.presence import presence_range
from apps.school.models import Lunch, SchoolDaySchedule
from apps.shopping.transfer import week_needs

MONDAY = datetime.date(2026, 11, 16)


class PresenceTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Khadija")
        self.partner = join(self.family, "Lhousseine")
        self.aliyah = make_child_profile(self.family, "Aliyah")
        self.zayd = make_child_profile(self.family, "Zayd")
        for child in (self.aliyah, self.zayd):
            for weekday in (0, 1, 3, 4):
                SchoolDaySchedule.objects.create(person=child, weekday=weekday, lunch=Lunch.CANTEEN)

    def presence(self, day, meal):
        return presence_range(self.family, MONDAY, 7)[(day, meal)]

    def test_canteen_children_are_away_at_lunch_only(self):
        lunch = self.presence(MONDAY, Meal.LUNCH)
        self.assertEqual(lunch.count, 2)
        self.assertEqual(lunch.explanation, "sans Aliyah, Zayd")
        self.assertEqual(self.presence(MONDAY, Meal.DINNER).count, 4)
        wednesday = MONDAY + datetime.timedelta(days=2)
        self.assertEqual(self.presence(wednesday, Meal.LUNCH).count, 4)  # pas d'école

    def test_absent_person_is_not_counted(self):
        Absence.objects.create(
            family=self.family,
            person=self.zayd,
            kind=AbsenceKind.OTHER,
            start_date=MONDAY,
            end_date=MONDAY,
        )
        self.assertEqual(self.presence(MONDAY, Meal.DINNER).count, 3)

    def test_shopping_quantities_follow_the_number_at_table(self):
        soup = Recipe.objects.create(family=self.family, name="Harira", servings=4)
        RecipeIngredient.objects.create(
            recipe=soup, name="lentilles", quantity=Decimal("200"), unit="g"
        )
        RecipeIngredient.objects.create(
            recipe=soup, name="oignon", quantity=Decimal("1"), unit="piece"
        )
        # Lundi midi : 2 à table (enfants à la cantine) → moitié ; dîner avec invités : 6 → ×1,5.
        MealSlot.objects.create(
            family=self.family, date=MONDAY, meal=Meal.LUNCH, kind=MealKind.RECIPE, recipe=soup
        )
        MealSlot.objects.create(
            family=self.family,
            date=MONDAY,
            meal=Meal.DINNER,
            kind=MealKind.RECIPE,
            recipe=soup,
            guests=6,
        )
        needs = {n.name: n for n in week_needs(self.family, MONDAY)}
        self.assertEqual(needs["lentilles"].quantity, Decimal("400.00"))  # 100 + 300
        self.assertEqual(needs["oignon"].quantity, Decimal("2"))  # 0,5 + 1,5

    def test_pieces_are_rounded_up(self):
        stew = Recipe.objects.create(family=self.family, name="Tajine", servings=4)
        RecipeIngredient.objects.create(
            recipe=stew, name="citron", quantity=Decimal("1"), unit="piece"
        )
        MealSlot.objects.create(
            family=self.family,
            date=MONDAY,
            meal=Meal.DINNER,
            kind=MealKind.RECIPE,
            recipe=stew,
            guests=5,
        )
        self.assertEqual(week_needs(self.family, MONDAY)[0].quantity, Decimal("2"))  # 1,25 → 2
