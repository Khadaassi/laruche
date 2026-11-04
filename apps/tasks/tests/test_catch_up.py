"""Rattrapage : tâches rattrapables oubliées hier, et correction des jours passés par un parent."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.absences.models import Absence, AbsenceKind
from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.stars.models import DayStar
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period
from apps.tasks.selectors import catch_up_for

TUESDAY = datetime.date(2026, 9, 29)
MONDAY = TUESDAY - datetime.timedelta(days=1)
# Mardi 19h à Paris (UTC+2).
TUESDAY_7PM = datetime.datetime(2026, 9, 29, 17, 0, tzinfo=datetime.UTC)


@mock.patch("django.utils.timezone.now", return_value=TUESDAY_7PM)
class CatchUpTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        self.teeth = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.homework = Task.objects.create(
            person=self.lina, title="Devoirs", period=Period.EVENING, catch_up=True
        )
        TaskCompletion.objects.create(task=self.teeth, date=MONDAY)
        self.client.force_login(self.kid)

    def url(self, task):
        return reverse("display:catch_up", args=[self.lina.pk, task.pk])

    def test_only_catch_up_tasks_left_undone_yesterday(self, _now):
        self.assertEqual(catch_up_for(self.family, TUESDAY), [self.homework])
        TaskCompletion.objects.create(task=self.homework, date=MONDAY)
        self.assertEqual(catch_up_for(self.family, TUESDAY), [])

    def test_nothing_to_catch_up_after_an_absence(self, _now):
        Absence.objects.create(
            family=self.family,
            person=self.lina,
            kind=AbsenceKind.SICK,
            start_date=MONDAY,
            end_date=MONDAY,
        )
        self.assertEqual(catch_up_for(self.family, TUESDAY), [])

    def test_board_shows_the_catch_up_section(self, _now):
        board = self.get(reverse("display:board"))
        self.assertContains(board, "À rattraper d'hier")

    def test_catching_up_recovers_yesterdays_star(self, _now):
        response = self.htmx_post(self.url(self.homework), {"done": "on"})
        self.assertContains(response, "Hier rattrapé : +1 étoile !")
        self.assertTrue(TaskCompletion.objects.filter(task=self.homework, date=MONDAY).exists())
        star = DayStar.objects.get(person=self.lina, date=MONDAY)
        self.assertTrue(star.celebrated)  # pas de plein écran « Journée terminée ! »

    def test_regular_task_cannot_be_caught_up(self, _now):
        self.assertEqual(self.htmx_post(self.url(self.teeth), {"done": "on"}).status_code, 404)

    def test_child_cannot_catch_up_for_a_sibling(self, _now):
        other = join(self.family, "Noah")
        self.client.force_login(other)
        self.assertEqual(self.htmx_post(self.url(self.homework), {"done": "on"}).status_code, 403)


@mock.patch("django.utils.timezone.now", return_value=TUESDAY_7PM)
class ParentCorrectionTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        self.task = Task.objects.create(person=self.lina, title="Lecture", period=Period.EVENING)
        self.client.force_login(self.parent)

    def test_parent_sees_a_past_day(self, _now):
        page = self.get(reverse("tasks:home"), {"jour": MONDAY.isoformat()})
        self.assertContains(page, "Correction après coup")
        self.assertContains(page, 'name="jour" value="2026-09-28"')

    def test_parent_ticks_a_past_day_and_the_star_follows(self, _now):
        url = reverse("tasks:toggle", args=[self.task.pk])
        self.htmx_post(url, {"done": "on", "jour": MONDAY.isoformat()})
        self.assertTrue(TaskCompletion.objects.filter(task=self.task, date=MONDAY).exists())
        self.assertTrue(DayStar.objects.filter(person=self.lina, date=MONDAY).exists())

    def test_too_old_or_future_days_are_refused(self, _now):
        url = reverse("tasks:toggle", args=[self.task.pk])
        for day in (TUESDAY - datetime.timedelta(days=8), TUESDAY + datetime.timedelta(days=1)):
            response = self.htmx_post(url, {"done": "on", "jour": day.isoformat()})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(
                self.get(reverse("tasks:home"), {"jour": day.isoformat()}).status_code, 404
            )

    def test_child_account_cannot_correct(self, _now):
        self.client.force_login(self.kid)
        url = reverse("tasks:toggle", args=[self.task.pk])
        self.htmx_post(url, {"done": "on", "jour": MONDAY.isoformat()})
        self.assertFalse(TaskCompletion.objects.filter(task=self.task, date=MONDAY).exists())
