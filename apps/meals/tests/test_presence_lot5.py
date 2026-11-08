"""Présences réelles : absences à effets séparés, vacances scolaires, menu assisté, courses."""

import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.absences.models import Absence, AbsenceKind
from apps.absences.selectors import absences_on
from apps.families.tests.factories import (
    SecureClientMixin,
    join,
    make_child_profile,
    make_family,
)
from apps.holidays.models import SchoolHoliday
from apps.meals.models import Meal, MealKind, MealPreferences, MealSlot, Recipe, RecipeIngredient
from apps.meals.presence import presence_range
from apps.meals.suggest import empty_slots
from apps.school.models import Lunch, SchoolDaySchedule
from apps.school.selectors import school_days_for
from apps.shopping.transfer import build_plan, week_needs
from apps.tasks.models import Task
from apps.tasks.periods import Period
from apps.tasks.selectors import tasks_for_day

MONDAY = datetime.date(2026, 11, 16)
TUESDAY = MONDAY + datetime.timedelta(days=1)
SUNDAY_6PM = datetime.datetime(2026, 11, 15, 17, 0, tzinfo=datetime.UTC)


class Fixture:
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Khadija")
        self.aliyah = make_child_profile(self.family, "Aliyah")
        self.zayd = make_child_profile(self.family, "Zayd")
        for child in (self.aliyah, self.zayd):
            for weekday in (0, 1, 3, 4):
                SchoolDaySchedule.objects.create(person=child, weekday=weekday, lunch=Lunch.CANTEEN)

    def absent(self, person, kind, **effects):
        return Absence.objects.create(
            family=self.family,
            person=person,
            kind=kind,
            start_date=MONDAY,
            end_date=MONDAY,
            **effects,
        )

    def presence(self, day, meal):
        return presence_range(self.family, MONDAY, 7)[(day, meal)]

    def lunches(self):
        return [d for d, m in empty_slots(self.family, MONDAY) if m == Meal.LUNCH]


@mock.patch("django.utils.timezone.now", return_value=SUNDAY_6PM)
class AbsenceEffectsTests(Fixture, TestCase):
    def test_sick_child_skips_tasks_and_school_but_eats_at_home(self, _now):
        self.absent(self.zayd, AbsenceKind.SICK, eats_at_home=True)
        Task.objects.create(person=self.zayd, title="Dents", period=Period.MORNING)
        self.assertEqual(list(tasks_for_day(self.family, MONDAY)), [])
        self.assertTrue(school_days_for(self.family, MONDAY)[self.zayd.pk].absence)
        lunch = self.presence(MONDAY, Meal.LUNCH)
        self.assertEqual(lunch.count, 2)  # Zayd mange à la maison, Aliyah à la cantine
        self.assertEqual(lunch.explanation, "sans Aliyah")
        self.assertEqual(self.presence(MONDAY, Meal.DINNER).count, 3)

    def test_absence_away_from_meals_removes_the_person(self, _now):
        self.absent(self.zayd, AbsenceKind.OTHER)
        self.assertEqual(self.presence(MONDAY, Meal.DINNER).count, 2)

    def test_effects_are_independent(self, _now):
        self.absent(self.zayd, AbsenceKind.OTHER, skips_tasks=False, misses_school=False)
        Task.objects.create(person=self.zayd, title="Dents", period=Period.MORNING)
        self.assertEqual([t.title for t in tasks_for_day(self.family, MONDAY)], ["Dents"])
        self.assertFalse(school_days_for(self.family, MONDAY)[self.zayd.pk].absence)
        self.assertFalse(absences_on(self.family, MONDAY).is_absent(self.zayd.pk))
        self.assertTrue(absences_on(self.family, MONDAY).misses_meals(self.zayd.pk))

    def test_school_holiday_ignores_the_weekly_schedule(self, _now):
        SchoolHoliday.objects.create(
            family=self.family, name="Vacances", start_date=MONDAY, end_date=MONDAY
        )
        self.assertNotIn(self.zayd.pk, school_days_for(self.family, MONDAY))
        self.assertEqual(self.presence(MONDAY, Meal.LUNCH).count, 3)
        self.assertIn(self.zayd.pk, school_days_for(self.family, TUESDAY))


@mock.patch("django.utils.timezone.now", return_value=SUNDAY_6PM)
class SuggestFromPresenceTests(Fixture, SecureClientMixin, TestCase):
    def test_lunch_when_a_child_is_at_home(self, _now):
        wednesday = MONDAY + datetime.timedelta(days=2)
        self.assertEqual(
            self.lunches(),
            [wednesday, MONDAY + datetime.timedelta(5), MONDAY + datetime.timedelta(6)],
        )

    def test_holiday_monday_and_sick_child_get_a_lunch(self, _now):
        SchoolHoliday.objects.create(
            family=self.family, name="Vacances", start_date=MONDAY, end_date=MONDAY
        )
        Absence.objects.create(
            family=self.family,
            person=self.zayd,
            kind=AbsenceKind.SICK,
            eats_at_home=True,
            start_date=TUESDAY,
            end_date=TUESDAY,
        )
        self.assertIn(MONDAY, self.lunches())
        self.assertIn(TUESDAY, self.lunches())
        self.assertNotIn(TUESDAY + datetime.timedelta(days=2), self.lunches())  # jeudi : cantine

    def test_adult_lunches_preference(self, _now):
        self.assertNotIn(MONDAY, self.lunches())
        MealPreferences.objects.create(family=self.family, adult_lunches=True)
        self.assertIn(MONDAY, self.lunches())

    def test_nobody_at_home_means_no_meal(self, _now):
        Absence.objects.create(
            family=self.family,
            person=None,
            kind=AbsenceKind.VACATION,
            start_date=MONDAY,
            end_date=MONDAY + datetime.timedelta(days=6),
        )
        self.assertEqual(empty_slots(self.family, MONDAY), [])

    def test_without_school_schedule_weekday_lunches_are_not_guessed(self, _now):
        SchoolDaySchedule.objects.all().delete()
        self.assertEqual([d.weekday() for d in self.lunches()], [2, 5, 6])

    def test_preferences_endpoint_is_parent_only(self, _now):
        url = reverse("meals:preferences") + "?semaine=2026-11-16"
        self.client.force_login(self.parent)
        self.client.post(url, {"adult_lunches": "on"})
        self.assertTrue(MealPreferences.for_family(self.family).adult_lunches)
        self.client.post(url, {})
        self.assertFalse(MealPreferences.for_family(self.family).adult_lunches)
        other = make_family()
        stranger = join(other, "Autre")
        self.client.force_login(stranger)
        self.client.post(url, {"adult_lunches": "on"})
        self.assertFalse(MealPreferences.for_family(self.family).adult_lunches)


class UnattendedTransferTests(Fixture, TestCase):
    def test_meal_nobody_eats_is_not_sent_but_reported(self):
        soup = Recipe.objects.create(family=self.family, name="Harira", servings=4)
        RecipeIngredient.objects.create(
            recipe=soup, name="lentilles", quantity=Decimal("200"), unit="g"
        )
        Absence.objects.create(
            family=self.family,
            person=None,
            kind=AbsenceKind.VACATION,
            start_date=MONDAY,
            end_date=MONDAY,
        )
        slot = MealSlot.objects.create(
            family=self.family, date=MONDAY, meal=Meal.DINNER, kind=MealKind.RECIPE, recipe=soup
        )
        self.assertEqual(week_needs(self.family, MONDAY), [])
        self.assertEqual(build_plan(self.family, MONDAY).unattended, [slot])
        slot.guests = 2
        slot.save()
        self.assertEqual(week_needs(self.family, MONDAY)[0].quantity, Decimal("100"))
        self.assertEqual(build_plan(self.family, MONDAY).unattended, [])
