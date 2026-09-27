"""Étoile du jour : +1 quand toute la journée d'un enfant est cochée, jamais plus."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.absences.models import Absence, AbsenceKind
from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family
from apps.household.models import ChoreCompletion, HouseholdChore
from apps.stars.models import DayStar
from apps.stars.selectors import balances
from apps.stars.services import award_day_star, claim_day_celebration
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
MONDAY = datetime.date(2026, 9, 28)
# Marqueur de la célébration plein écran « Journée terminée ! ».
OVERLAY = 'x-data="celebrationOverlay"'


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


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class DayStarScreenTests(SecureClientMixin, TestCase):
    """Parcours réels : cochage depuis l'écran partagé, l'accueil parent, le semainier."""

    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        self.morning = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.evening = Task.objects.create(person=self.lina, title="Pyjama", period=Period.EVENING)
        self.client.force_login(self.kid)

    def tick(self, task, done=True):
        url = reverse("display:toggle", args=[self.lina.pk, task.pk])
        return self.htmx_post(url, {"done": "on"} if done else {})

    def test_last_task_celebrates_once(self, _now):
        self.assertNotContains(self.tick(self.morning), "Journée terminée")
        last = self.tick(self.evening)
        self.assertContains(last, OVERLAY)
        self.assertContains(last, "Journée terminée !")
        self.assertContains(last, "Bravo Lina, tout est fait aujourd'hui !")
        self.assertContains(last, "+1 étoile · 1 étoile")
        self.assertContains(last, "1 étoile")
        # Décocher / recocher, recharger l'écran : ni nouvelle étoile ni nouvelle fête.
        self.assertNotContains(self.tick(self.evening, done=False), "Journée terminée")
        self.assertNotContains(self.tick(self.evening), "Journée terminée")
        self.assertNotContains(self.get(reverse("display:board")), "Journée terminée")
        self.assertEqual(DayStar.objects.filter(person=self.lina).count(), 1)

    def test_unticking_keeps_the_star_on_screen(self, _now):
        self.tick(self.morning), self.tick(self.evening)
        response = self.tick(self.morning, done=False)
        self.assertContains(response, "1 étoile")

    def test_no_star_mention_on_ticked_tasks(self, _now):
        response = self.tick(self.morning)
        # La période est finie, pas la journée : pas d'étoile ni de fête.
        self.assertContains(response, "0 étoiles")
        self.assertNotContains(response, "Journée terminée")
        board = self.get(reverse("display:board"))
        self.assertContains(board, ">Fait</span>")
        self.assertNotContains(board, "Fait ! +1")

    def test_last_chore_completes_the_day(self, _now):
        chore = HouseholdChore.objects.create(
            family=self.family, title="Table", assignee=self.lina, start_date=MONDAY
        )
        self.tick(self.morning), self.tick(self.evening)
        self.assertFalse(DayStar.objects.exists())
        url = reverse("display:toggle_chore", args=[self.lina.pk, chore.pk])
        self.assertContains(self.htmx_post(url, {"done": "on"}), OVERLAY)

    def test_parent_ticking_the_last_task_announces_it_and_the_screen_celebrates(self, _now):
        tick(self.morning)
        self.client.force_login(self.parent)
        url = reverse("tasks:toggle", args=[self.evening.pk])
        response = self.htmx_post(url, {"done": "on"})
        self.assertContains(response, "Journée terminée pour Lina : +1 étoile")
        # Le parent voit aussi la célébration plein écran.
        self.assertContains(response, OVERLAY)
        # La fête des enfants n'est pas consommée par le parent : elle attend l'écran.
        board = self.get(reverse("display:board"))
        self.assertContains(board, OVERLAY)
        self.assertNotContains(self.get(reverse("display:board")), OVERLAY)

    def test_parent_other_ticks_announce_nothing(self, _now):
        self.client.force_login(self.parent)
        url = reverse("tasks:toggle", args=[self.morning.pk])
        self.assertNotContains(self.htmx_post(url, {"done": "on"}), "Journée terminée")

    def test_chore_ticked_on_the_week_planner_completes_the_day(self, _now):
        chore = HouseholdChore.objects.create(
            family=self.family, title="Table", assignee=self.lina, start_date=MONDAY
        )
        tick(self.morning), tick(self.evening)
        self.client.force_login(self.parent)
        url = reverse("household:toggle", args=[chore.pk, MONDAY.isoformat()])
        self.assertEqual(self.htmx_post(url, {"done": "on"}).status_code, 204)
        self.assertTrue(DayStar.objects.filter(person=self.lina, date=MONDAY).exists())

    def test_other_family_cannot_complete_the_day(self, _now):
        stranger = join(make_family(name="Voisins"), "Tom")
        self.client.force_login(stranger)
        tick(self.morning)
        url = reverse("display:toggle", args=[self.lina.pk, self.evening.pk])
        self.assertEqual(self.htmx_post(url, {"done": "on"}).status_code, 404)
        self.assertFalse(DayStar.objects.exists())
