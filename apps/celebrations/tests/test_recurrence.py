import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.celebrations.models import Celebration, CelebrationTodo, GiftItem, RecipeIdea
from apps.celebrations.services import next_date, roll_over_recurring
from apps.families.tests.factories import SecureClientMixin, join, make_family

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
TODAY = datetime.date(2026, 9, 28)


class NextDateTests(TestCase):
    def test_same_day_next_year(self):
        self.assertEqual(next_date(datetime.date(2026, 3, 14), TODAY), datetime.date(2027, 3, 14))

    def test_february_29_falls_back_to_28(self):
        self.assertEqual(
            next_date(datetime.date(2024, 2, 29), datetime.date(2024, 3, 1)),
            datetime.date(2025, 2, 28),
        )

    def test_missed_years_are_skipped(self):
        self.assertEqual(next_date(datetime.date(2023, 5, 2), TODAY), datetime.date(2027, 5, 2))


class RollOverTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.birthday = Celebration.objects.create(
            family=self.family,
            name="Anniversaire de Lina",
            date=datetime.date(2026, 9, 20),
            recurs_yearly=True,
        )
        CelebrationTodo.objects.create(celebration=self.birthday, title="Gâteau", done=True)
        GiftItem.objects.create(celebration=self.birthday, item="Vélo")
        RecipeIdea.objects.create(
            celebration=self.birthday, name="Gâteau au chocolat", notes="Pour 10"
        )

    def test_passed_recurring_celebration_is_recreated_next_year(self):
        (following,) = roll_over_recurring(self.family, TODAY)
        self.assertEqual(
            (following.name, following.date), ("Anniversaire de Lina", datetime.date(2027, 9, 20))
        )
        self.assertTrue(following.recurs_yearly)
        self.assertEqual(following.previous, self.birthday)
        self.assertEqual(following.family, self.family)

    def test_todos_and_gifts_start_empty_recipes_are_kept(self):
        (following,) = roll_over_recurring(self.family, TODAY)
        self.assertFalse(following.todos.exists())
        self.assertFalse(following.gifts.exists())
        self.assertEqual(
            [(r.name, r.notes) for r in following.recipes.all()],
            [("Gâteau au chocolat", "Pour 10")],
        )
        # L'année passée garde tout.
        self.assertEqual((self.birthday.todos.count(), self.birthday.gifts.count()), (1, 1))

    def test_idempotent(self):
        roll_over_recurring(self.family, TODAY)
        self.assertEqual(roll_over_recurring(self.family, TODAY), [])
        self.assertEqual(Celebration.objects.count(), 2)

    def test_chain_continues_the_following_year(self):
        (following,) = roll_over_recurring(self.family, TODAY)
        (third,) = roll_over_recurring(self.family, datetime.date(2027, 9, 21))
        self.assertEqual((third.date, third.previous), (datetime.date(2028, 9, 20), following))

    def test_not_before_the_day_is_over(self):
        self.assertEqual(roll_over_recurring(self.family, datetime.date(2026, 9, 20)), [])

    def test_non_recurring_is_never_recreated(self):
        Celebration.objects.create(family=self.family, name="Aïd", date=datetime.date(2026, 5, 27))
        roll_over_recurring(self.family, TODAY)
        self.assertEqual(Celebration.objects.filter(name="Aïd").count(), 1)

    def test_other_family_untouched(self):
        other = make_family(name="Voisins")
        Celebration.objects.create(
            family=other, name="Leur fête", date=datetime.date(2026, 1, 1), recurs_yearly=True
        )
        roll_over_recurring(self.family, TODAY)
        self.assertEqual(Celebration.objects.filter(family=other).count(), 1)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class RecurrenceViewsTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")

    def test_create_recurring_from_form(self, _now):
        self.client.force_login(self.parent)
        self.post(
            reverse("celebrations:index"),
            {"name": "Anniversaire", "date": "2026-10-03", "recurs_yearly": "on"},
        )
        self.assertTrue(Celebration.objects.get().recurs_yearly)

    def test_listing_rolls_over_and_shows_next_occurrence(self, _now):
        Celebration.objects.create(
            family=self.family,
            name="Anniversaire",
            date=datetime.date(2026, 9, 1),
            recurs_yearly=True,
        )
        self.client.force_login(self.parent)
        response = self.get(reverse("celebrations:index"))
        upcoming = response.context["upcoming"]
        self.assertEqual(
            [(c.name, c.date) for c in upcoming], [("Anniversaire", datetime.date(2027, 9, 1))]
        )
        self.assertContains(response, "chaque année")

    def test_shared_screen_also_rolls_over(self, _now):
        Celebration.objects.create(
            family=self.family,
            name="Anniversaire",
            date=datetime.date(2026, 9, 1),
            recurs_yearly=True,
        )
        self.client.force_login(self.kid)
        self.assertContains(self.get(reverse("display:celebrations")), "Anniversaire")

    def test_child_cannot_toggle_recurrence(self, _now):
        celebration = Celebration.objects.create(
            family=self.family, name="X", date=datetime.date(2026, 10, 1)
        )
        self.client.force_login(self.kid)
        url = reverse("celebrations:edit", args=[celebration.pk])
        self.assertEqual(
            self.post(url, {"name": "X", "date": "2026-10-01", "recurs_yearly": "on"}).status_code,
            403,
        )
        celebration.refresh_from_db()
        self.assertFalse(celebration.recurs_yearly)
