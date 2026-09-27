"""Étoile du jour : +1 quand toute la journée d'un enfant est cochée, jamais plus."""

import datetime
from unittest import mock

from django.test import TestCase

from apps.absences.models import Absence, AbsenceKind
from apps.families.tests.factories import join, make_child_profile, make_family
from apps.household.models import ChoreCompletion, HouseholdChore
from apps.stars.models import DayStar
from apps.stars.selectors import balances
from apps.stars.services import award_day_star, claim_day_celebration
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
MONDAY = datetime.date(2026, 9, 28)


def tick(task, day=MONDAY):
    TaskCompletion.objects.get_or_create(task=task, date=day)


def untick(task, day=MONDAY):
    TaskCompletion.objects.filter(task=task, date=day).delete()


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class AwardDayStarTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        self.morning = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.evening = Task.objects.create(person=self.lina, title="Pyjama", period=Period.EVENING)

    def earned(self):
        return balances(self.family)[self.lina.pk].earned

    def test_no_star_until_every_period_is_done(self, _now):
        tick(self.morning)
        self.assertFalse(award_day_star(self.lina, MONDAY))
        self.assertEqual(self.earned(), 0)
        tick(self.evening)
        self.assertTrue(award_day_star(self.lina, MONDAY))
        self.assertEqual(self.earned(), 1)

    def test_untick_then_retick_gives_no_second_star(self, _now):
        tick(self.morning), tick(self.evening)
        self.assertTrue(award_day_star(self.lina, MONDAY))
        untick(self.evening)
        self.assertFalse(award_day_star(self.lina, MONDAY))
        tick(self.evening)
        self.assertFalse(award_day_star(self.lina, MONDAY))
        self.assertEqual(DayStar.objects.filter(person=self.lina).count(), 1)
        self.assertEqual(self.earned(), 1)

    def test_unticking_afterwards_keeps_the_star(self, _now):
        tick(self.morning), tick(self.evening)
        award_day_star(self.lina, MONDAY)
        untick(self.morning), untick(self.evening)
        self.assertEqual(self.earned(), 1)

    def test_chore_assigned_to_the_child_counts(self, _now):
        chore = HouseholdChore.objects.create(
            family=self.family, title="Table", assignee=self.lina, start_date=MONDAY
        )
        tick(self.morning), tick(self.evening)
        self.assertFalse(award_day_star(self.lina, MONDAY))
        ChoreCompletion.objects.create(chore=chore, date=MONDAY)
        self.assertTrue(award_day_star(self.lina, MONDAY))

    def test_a_sibling_chore_does_not_count(self, _now):
        HouseholdChore.objects.create(
            family=self.family, title="Poubelles", assignee=self.noah, start_date=MONDAY
        )
        tick(self.morning), tick(self.evening)
        self.assertTrue(award_day_star(self.lina, MONDAY))

    def test_tasks_not_scheduled_today_do_not_count(self, _now):
        Task.objects.create(
            person=self.lina,
            title="Piscine",
            period=Period.NOON,
            weekdays=1 << 2,  # mercredi
        )
        tick(self.morning), tick(self.evening)
        self.assertTrue(award_day_star(self.lina, MONDAY))

    def test_nothing_planned_or_absent_gives_no_star(self, _now):
        self.assertFalse(award_day_star(self.noah, MONDAY))
        Absence.objects.create(
            family=self.family,
            person=self.lina,
            kind=AbsenceKind.SICK,
            start_date=MONDAY,
            end_date=MONDAY,
        )
        tick(self.morning), tick(self.evening)
        self.assertFalse(award_day_star(self.lina, MONDAY))
        self.assertFalse(DayStar.objects.exists())

    def test_parents_never_get_a_day_star(self, _now):
        parent = join(self.family, "Sam").person
        task = Task.objects.create(person=parent, title="Courses", period=Period.NOON)
        tick(task)
        self.assertFalse(award_day_star(parent, MONDAY))

    def test_no_star_for_a_future_day(self, _now):
        tomorrow = MONDAY + datetime.timedelta(days=1)
        tick(self.morning, tomorrow), tick(self.evening, tomorrow)
        self.assertFalse(award_day_star(self.lina, tomorrow))

    def test_one_star_per_day_on_several_days(self, _now):
        saturday = MONDAY - datetime.timedelta(days=2)
        for day in (saturday, MONDAY):
            tick(self.morning, day), tick(self.evening, day)
            self.assertTrue(award_day_star(self.lina, day))
        self.assertEqual(self.earned(), 2)

    def test_celebration_is_claimed_once(self, _now):
        tick(self.morning), tick(self.evening)
        self.assertFalse(claim_day_celebration(self.lina, MONDAY))  # pas encore d'étoile
        award_day_star(self.lina, MONDAY)
        self.assertTrue(claim_day_celebration(self.lina, MONDAY))
        self.assertFalse(claim_day_celebration(self.lina, MONDAY))
