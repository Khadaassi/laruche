"""Solde de départ : étoiles gagnées avant La Ruche, reprises telles quelles."""

import datetime
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family
from apps.stars.models import StarOpeningBalance, TierCelebration
from apps.stars.selectors import balances, pot
from apps.stars.services import (
    OpeningBalanceError,
    claim_tier_celebration,
    grant_opening_balance,
    spend_from_pot,
)

from .test_stars import earn

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)


class OpeningBalanceTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")

    def test_counts_exactly_as_earned_stars(self):
        grant_opening_balance(self.lina, 7, "Reprise")
        grant_opening_balance(self.noah, 5, "Reprise")
        stars = balances(self.family)
        self.assertEqual((stars[self.lina.pk].earned, stars[self.noah.pk].earned), (7, 5))
        self.assertEqual(pot(self.family), 12)

    def test_adds_to_day_stars_and_spends(self):
        grant_opening_balance(self.lina, 7, "Reprise")
        earn(self.lina, 4)
        spend_from_pot(self.family, 3, "Glace")
        balance = balances(self.family)[self.lina.pk]
        self.assertEqual((balance.earned, balance.balance, balance.tier), (11, 8, 1))

    def test_only_once_per_child(self):
        grant_opening_balance(self.lina, 7, "Reprise")
        with self.assertRaises(OpeningBalanceError):
            grant_opening_balance(self.lina, 7, "Reprise")
        # La base refuse aussi un doublon écrit sans passer par le service.
        with self.assertRaises(IntegrityError), transaction.atomic():
            StarOpeningBalance.objects.create(person=self.lina, amount=1, reason="Doublon")
        self.assertEqual(balances(self.family)[self.lina.pk].earned, 7)

    def test_refused_for_a_parent_or_a_non_positive_amount(self):
        parent = join(self.family, "Sam").person
        with self.assertRaises(OpeningBalanceError):
            grant_opening_balance(parent, 5, "Reprise")
        for amount in (0, -3):
            with self.assertRaises(OpeningBalanceError):
                grant_opening_balance(self.lina, amount, "Reprise")
        self.assertFalse(StarOpeningBalance.objects.exists())

    def test_database_refuses_zero(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            StarOpeningBalance.objects.create(person=self.lina, amount=0, reason="Vide")

    def test_other_family_isolated(self):
        stranger = make_child_profile(make_family(name="Voisins"), "Tom")
        grant_opening_balance(stranger, 30, "Reprise")
        self.assertEqual(pot(self.family), 0)

    def test_tier_reached_by_the_opening_balance_is_not_celebrated_again(self):
        grant_opening_balance(self.lina, 23, "Reprise")
        self.assertEqual(TierCelebration.objects.get(person=self.lina).tier, 2)
        self.assertIsNone(claim_tier_celebration(balances(self.family)[self.lina.pk]))
        # Le palier suivant, franchi dans La Ruche, est bien fêté.
        earn(self.lina, 7)
        self.assertEqual(claim_tier_celebration(balances(self.family)[self.lina.pk]), 3)

    def test_small_balance_creates_no_tier_row(self):
        grant_opening_balance(self.lina, 7, "Reprise")
        self.assertFalse(TierCelebration.objects.exists())


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class OpeningBalanceScreenTests(SecureClientMixin, TestCase):
    def test_shared_screen_and_parent_home_show_the_opening_balance(self, _now):
        family = make_family()
        parent = join(family, "Sam")
        lina = make_child_profile(family, "Lina")
        grant_opening_balance(lina, 7, "Reprise")
        self.client.force_login(parent)
        board = self.get(reverse("display:board"))
        self.assertContains(board, "7 étoiles")
        self.assertContains(board, "palier dans 3")
        self.assertNotContains(board, "Palier 1")
