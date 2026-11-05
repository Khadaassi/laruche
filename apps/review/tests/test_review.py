"""Revue du dimanche : semaine visée, page guidée, carte d'accueil, isolation."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.review.models import WeeklyReview
from apps.review.selectors import review_monday

SUNDAY_6PM = datetime.datetime(2026, 11, 15, 17, 0, tzinfo=datetime.UTC)
TUESDAY_6PM = datetime.datetime(2026, 11, 10, 17, 0, tzinfo=datetime.UTC)
NEXT_MONDAY = datetime.date(2026, 11, 16)


class ReviewMondayTests(TestCase):
    def test_from_friday_we_prepare_next_week(self):
        d = datetime.date
        self.assertEqual(review_monday(d(2026, 11, 12)), d(2026, 11, 9))  # jeudi
        self.assertEqual(review_monday(d(2026, 11, 13)), NEXT_MONDAY)  # vendredi
        self.assertEqual(review_monday(d(2026, 11, 15)), NEXT_MONDAY)  # dimanche


class ReviewPageTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.client.force_login(self.parent)

    @mock.patch("django.utils.timezone.now", return_value=SUNDAY_6PM)
    def test_home_card_until_done(self, _now):
        self.assertContains(self.get(reverse("tasks:home")), "Revue de la semaine")
        page = self.get(reverse("review:week"))
        self.assertContains(page, "Semaine du 16 novembre")
        self.assertContains(page, "La semaine est prête")
        self.post(reverse("review:done"), {"semaine": NEXT_MONDAY.isoformat()})
        self.assertTrue(WeeklyReview.objects.filter(family=self.family, week=NEXT_MONDAY).exists())
        self.assertNotContains(self.get(reverse("tasks:home")), "Revue de la semaine")
        self.assertContains(self.get(reverse("review:week")), "Revue terminée")

    @mock.patch("django.utils.timezone.now", return_value=TUESDAY_6PM)
    def test_no_home_card_midweek(self, _now):
        self.assertNotContains(self.get(reverse("tasks:home")), "Revue de la semaine")

    @mock.patch("django.utils.timezone.now", return_value=SUNDAY_6PM)
    def test_children_cannot_review(self, _now):
        self.client.force_login(self.kid)
        self.assertNotEqual(self.get(reverse("review:week")).status_code, 200)
        self.post(reverse("review:done"), {"semaine": NEXT_MONDAY.isoformat()})
        self.assertFalse(WeeklyReview.objects.exists())

    @mock.patch("django.utils.timezone.now", return_value=SUNDAY_6PM)
    def test_bad_week_is_404(self, _now):
        self.assertEqual(self.get(reverse("review:week"), {"semaine": "x"}).status_code, 404)
