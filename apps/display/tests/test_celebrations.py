"""Célébrations renforcées : fin de routine, palier en plein écran, compteur, pluie."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.stars.models import StarOpeningBalance
from apps.tasks.models import Task
from apps.tasks.periods import Period

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class CelebrationTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        self.teeth = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.bed = Task.objects.create(person=self.lina, title="Lit", period=Period.MORNING)
        self.pyjama = Task.objects.create(person=self.lina, title="Pyjama", period=Period.EVENING)
        self.client.force_login(self.kid)

    def tick(self, task, done=True):
        url = reverse("display:toggle", args=[self.lina.pk, task.pk])
        return self.htmx_post(url, {"done": "on"} if done else {})

    def test_finishing_the_morning_routine_is_celebrated(self, _now):
        self.assertNotContains(self.tick(self.teeth), "Routine du matin terminée")
        response = self.tick(self.bed)
        self.assertContains(response, "Routine du matin terminée !")
        self.assertNotContains(response, "Journée terminée")  # le soir reste à faire

    def test_unticking_shows_nothing(self, _now):
        self.tick(self.teeth), self.tick(self.bed)
        self.assertNotContains(self.tick(self.bed, done=False), "terminée")

    def test_day_celebration_is_full_screen_with_rain_and_sound(self, _now):
        self.tick(self.teeth), self.tick(self.bed)
        last = self.tick(self.pyjama)
        self.assertContains(last, "Journée terminée !")
        self.assertContains(last, 'class="rain"')
        self.assertContains(last, 'data-sound="day"')

    def test_tier_is_now_full_screen(self, _now):
        StarOpeningBalance.objects.create(person=self.lina, amount=9, reason="reprise")
        self.tick(self.teeth), self.tick(self.bed)
        last = self.tick(self.pyjama)
        # Palier franchi avec la journée : annoncé dans le plein écran du jour.
        self.assertContains(last, "Palier 1 atteint !")
        self.assertNotContains(last, 'data-sound="tier"')

    def test_tier_alone_gets_its_own_full_screen(self, _now):
        StarOpeningBalance.objects.create(person=self.lina, amount=10, reason="reprise")
        board = self.get(reverse("display:board"))
        self.assertContains(board, 'data-sound="tier"')
        self.assertContains(board, "Palier 1 !")
        self.assertNotContains(self.get(reverse("display:board")), 'data-sound="tier"')
