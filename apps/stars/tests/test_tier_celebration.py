import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family
from apps.stars.models import TierCelebration
from apps.stars.selectors import balances
from apps.stars.services import claim_tier_celebration
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period

from .test_stars import earn

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
MONDAY = datetime.date(2026, 9, 28)


class ClaimTierTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.lina = make_child_profile(self.family, "Lina")

    def claim(self):
        return claim_tier_celebration(balances(self.family)[self.lina.pk])

    def test_nothing_before_first_tier(self):
        earn(self.lina, 9)
        self.assertIsNone(self.claim())

    def test_celebrated_once_per_tier(self):
        earn(self.lina, 10)
        self.assertEqual(self.claim(), 1)
        self.assertIsNone(self.claim())
        self.assertIsNone(self.claim())

    def test_untick_then_retick_does_not_celebrate_again(self):
        earn(self.lina, 10)
        self.claim()
        completion = TaskCompletion.objects.filter(task__person=self.lina).first()
        task, date = completion.task, completion.date
        completion.delete()
        self.assertIsNone(self.claim())
        TaskCompletion.objects.create(task=task, date=date)
        self.assertIsNone(self.claim())

    def test_next_tier_is_celebrated(self):
        earn(self.lina, 10)
        self.claim()
        earn(self.lina, 10, start=MONDAY - datetime.timedelta(days=100))
        self.assertEqual(self.claim(), 2)

    def test_several_tiers_at_once_give_a_single_celebration(self):
        earn(self.lina, 25)
        self.assertEqual(self.claim(), 2)
        self.assertIsNone(self.claim())
        self.assertEqual(TierCelebration.objects.get(person=self.lina).tier, 2)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class SharedScreenTierTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        earn(self.lina, 9, start=MONDAY - datetime.timedelta(days=1))
        self.task = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.client.force_login(self.kid)

    def tick(self, done=True):
        url = reverse("display:toggle", args=[self.lina.pk, self.task.pk])
        return self.htmx_post(url, {"done": "on"} if done else {})

    def test_crossing_a_tier_celebrates_in_the_toggle_response_once(self, _now):
        first = self.tick()
        self.assertContains(first, "Palier 1 !")
        self.assertContains(first, "Bravo Lina, 10 étoiles gagnées !")
        # Décocher / recocher, puis recharger l'écran : pas de doublon.
        self.assertNotContains(self.tick(done=False), "Palier 1 !")
        self.assertNotContains(self.tick(), "Palier 1 !")
        self.assertNotContains(self.get(reverse("display:board")), "Palier 1 !")

    def test_tier_reached_elsewhere_is_celebrated_on_next_board_load(self, _now):
        TaskCompletion.objects.create(task=self.task, date=MONDAY)  # coché par un parent
        self.assertContains(self.get(reverse("display:board")), "Palier 1 !")
        self.assertNotContains(self.get(reverse("display:board")), "Palier 1 !")

    def test_parent_tasks_never_trigger_a_celebration(self, _now):
        earn(self.parent.person, 30)
        self.assertNotContains(self.get(reverse("display:board")), "Palier")
