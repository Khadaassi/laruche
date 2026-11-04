"""Étoiles manquantes : oublis des périodes passées visibles, rattrapage des jours récents."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.stars.models import DayStar
from apps.stars.services import CATCH_UP_DAYS, award_missing_day_stars
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period, earlier_periods

MONDAY = datetime.date(2026, 9, 28)
# 19h à Paris (UTC+2) : période du soir.
MONDAY_7PM = datetime.datetime(2026, 9, 28, 17, 0, tzinfo=datetime.UTC)


class EarlierPeriodsTests(TestCase):
    def test_order_of_the_day(self):
        self.assertEqual(earlier_periods(Period.MORNING), [])
        self.assertEqual(earlier_periods(Period.NOON), [Period.MORNING])
        self.assertEqual(earlier_periods(Period.EVENING), [Period.MORNING, Period.NOON])


@mock.patch("django.utils.timezone.now", return_value=MONDAY_7PM)
class OverdueOnSharedScreenTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        join(self.family, "Sam")  # premier inscrit = parent
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        self.morning = Task.objects.create(
            person=self.lina, title="Lit fait", period=Period.MORNING
        )
        self.evening = Task.objects.create(person=self.lina, title="Pyjama", period=Period.EVENING)
        self.client.force_login(self.kid)

    def test_forgotten_morning_task_stays_visible_in_the_evening(self, _now):
        board = self.get(reverse("display:board"))
        self.assertContains(board, "Encore à faire plus tôt")
        self.assertContains(board, "Lit fait")

    def test_done_morning_task_is_not_repeated(self, _now):
        TaskCompletion.objects.create(task=self.morning, date=MONDAY)
        self.assertNotContains(self.get(reverse("display:board")), "Encore à faire plus tôt")

    def test_ticking_the_forgotten_task_completes_the_day(self, _now):
        TaskCompletion.objects.create(task=self.evening, date=MONDAY)
        url = reverse("display:toggle", args=[self.lina.pk, self.morning.pk])
        self.assertContains(self.htmx_post(url, {"done": "on"}), "Journée terminée !")
        self.assertTrue(DayStar.objects.filter(person=self.lina, date=MONDAY).exists())


@mock.patch("django.utils.timezone.now", return_value=MONDAY_7PM)
class CatchUpTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        self.done = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.left = Task.objects.create(person=self.lina, title="Lecture", period=Period.EVENING)
        self.yesterday = MONDAY - datetime.timedelta(days=1)
        TaskCompletion.objects.create(task=self.done, date=self.yesterday)

    def test_day_completed_by_removing_the_last_task_gets_its_star(self, _now):
        self.assertEqual(award_missing_day_stars(self.family, MONDAY), 0)
        self.left.delete()
        self.assertEqual(award_missing_day_stars(self.family, MONDAY), 1)
        self.assertTrue(DayStar.objects.filter(person=self.lina, date=self.yesterday).exists())
        # Idempotent.
        self.assertEqual(award_missing_day_stars(self.family, MONDAY), 0)

    def test_older_days_are_left_alone(self, _now):
        old = MONDAY - datetime.timedelta(days=CATCH_UP_DAYS + 1)
        TaskCompletion.objects.create(task=self.done, date=old)
        self.left.delete()
        award_missing_day_stars(self.family, MONDAY)
        self.assertFalse(DayStar.objects.filter(person=self.lina, date=old).exists())

    def test_opening_the_board_runs_the_catch_up(self, _now):
        self.left.delete()
        self.client.force_login(self.kid)
        self.get(reverse("display:board"))
        self.assertTrue(DayStar.objects.filter(person=self.lina, date=self.yesterday).exists())

    def test_parent_home_runs_the_catch_up(self, _now):
        self.left.delete()
        self.client.force_login(self.parent)
        self.get(reverse("tasks:home"))
        self.assertTrue(DayStar.objects.filter(person=self.lina, date=self.yesterday).exists())
