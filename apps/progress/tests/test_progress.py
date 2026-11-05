"""Page Progrès : calendrier du mois, tendance, tâches à encourager."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.absences.models import Absence, AbsenceKind
from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.progress.selectors import DayState, month_calendar, skipped_tasks, weekly_trend
from apps.stars.models import DayStar
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period

TODAY = datetime.date(2026, 11, 18)  # mercredi
NOON = datetime.datetime(2026, 11, 18, 11, 0, tzinfo=datetime.UTC)


def cell(weeks, day):
    return next(c for week in weeks for c in week if c.date == day)


@mock.patch("django.utils.timezone.now", return_value=NOON)
class ProgressTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        self.task = Task.objects.create(person=self.lina, title="Lecture", period=Period.EVENING)
        self.teeth = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)

    def test_calendar_states(self, _now):
        d = datetime.date
        DayStar.objects.create(person=self.lina, date=d(2026, 11, 2))
        TaskCompletion.objects.create(task=self.task, date=d(2026, 11, 3))
        Absence.objects.create(
            family=self.family,
            person=self.lina,
            kind=AbsenceKind.SICK,
            start_date=d(2026, 11, 4),
            end_date=d(2026, 11, 4),
        )
        weeks, stars = month_calendar(self.family, [self.lina], TODAY, TODAY)[self.lina.pk]
        self.assertEqual(stars, 1)
        self.assertEqual(cell(weeks, d(2026, 11, 2)).state, DayState.STAR)
        self.assertEqual(cell(weeks, d(2026, 11, 3)).state, DayState.PARTIAL)
        self.assertEqual(cell(weeks, d(2026, 11, 4)).state, DayState.ABSENT)
        self.assertEqual(cell(weeks, d(2026, 11, 5)).state, DayState.EMPTY)
        self.assertEqual(cell(weeks, d(2026, 11, 30)).state, DayState.FUTURE)
        # Novembre 2026 commence un dimanche : 6 cases vides avant.
        self.assertIsNone(weeks[0][5].date)
        self.assertTrue(all(len(week) == 7 for week in weeks))

    def test_weekly_trend(self, _now):
        DayStar.objects.create(person=self.lina, date=TODAY)
        DayStar.objects.create(person=self.lina, date=TODAY - datetime.timedelta(days=7))
        trend = weekly_trend([self.lina], TODAY)[self.lina.pk]
        self.assertEqual(len(trend), 8)
        self.assertEqual([n for _, n in trend][-2:], [1, 1])

    def test_skipped_tasks_lists_the_least_done(self, _now):
        for offset in range(1, 31):
            TaskCompletion.objects.create(
                task=self.teeth, date=TODAY - datetime.timedelta(days=offset)
            )
        for offset in range(1, 6):
            TaskCompletion.objects.create(
                task=self.task, date=TODAY - datetime.timedelta(days=offset)
            )
        rows = skipped_tasks(self.family, [self.lina], TODAY)[self.lina.pk]
        self.assertEqual([(t.title, done, due) for t, done, due in rows], [("Lecture", 5, 30)])

    def test_page_for_parents_only(self, _now):
        self.client.force_login(self.parent)
        page = self.get(reverse("progress:overview"))
        self.assertContains(page, "Novembre 2026")
        self.assertContains(page, "Étoiles par semaine")
        self.assertEqual(
            self.get(reverse("progress:overview"), {"mois": "2027-01"}).status_code, 404
        )
        self.assertEqual(self.get(reverse("progress:overview"), {"mois": "nope"}).status_code, 404)
        self.client.force_login(self.kid)
        self.assertNotEqual(self.get(reverse("progress:overview")).status_code, 200)

    def test_other_family_children_are_not_shown(self, _now):
        other = make_family()
        join(other, "Alex")
        stranger_kid = join(other, "Zoé")
        self.client.force_login(self.parent)
        self.assertNotContains(self.get(reverse("progress:overview")), stranger_kid.person.name)
