"""Mode vacances : l'essentiel donne l'étoile, le reste est en bonus."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.holidays.models import SchoolHoliday
from apps.holidays.services import add_zone_b
from apps.stars.models import DayStar
from apps.stars.services import award_day_star
from apps.tasks.models import HolidayMode, Task, TaskCompletion
from apps.tasks.periods import Period

# Lundi 21 décembre 2026, 19h à Paris (UTC+1) : vacances de Noël.
DAY = datetime.date(2026, 12, 21)
DAY_7PM = datetime.datetime(2026, 12, 21, 18, 0, tzinfo=datetime.UTC)


@mock.patch("django.utils.timezone.now", return_value=DAY_7PM)
class HolidayModeTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        self.prayer = Task.objects.create(
            person=self.lina,
            title="Prière",
            period=Period.EVENING,
            holiday_mode=HolidayMode.REQUIRED,
        )
        self.homework = Task.objects.create(
            person=self.lina,
            title="Devoirs",
            period=Period.EVENING,
            holiday_mode=HolidayMode.WEEKLY,
            weekly_target=3,
        )
        self.tidy = Task.objects.create(person=self.lina, title="Ranger", period=Period.EVENING)
        add_zone_b(self.family)

    def test_only_required_tasks_give_the_star_in_holidays(self, _now):
        TaskCompletion.objects.create(task=self.prayer, date=DAY)
        self.assertTrue(award_day_star(self.lina, DAY))

    def test_outside_holidays_everything_counts(self, _now):
        SchoolHoliday.objects.all().delete()
        TaskCompletion.objects.create(task=self.prayer, date=DAY)
        self.assertFalse(award_day_star(self.lina, DAY))

    def test_board_shows_holiday_banner_and_bonus(self, _now):
        self.client.force_login(self.kid)
        board = self.get(reverse("display:board"))
        self.assertContains(board, "Vacances de Noël")
        self.assertContains(board, "Bonus vacances")
        self.assertContains(board, "Devoirs · 0/3 cette semaine")

    def test_weekly_goal_counts_days_since_monday(self, _now):
        TaskCompletion.objects.create(task=self.homework, date=DAY)
        TaskCompletion.objects.create(task=self.homework, date=DAY - datetime.timedelta(days=1))
        self.client.force_login(self.kid)
        # Dimanche d'avant = semaine précédente : seul lundi compte.
        self.assertContains(self.get(reverse("display:board")), "Devoirs · 1/3 cette semaine")

    def test_ticking_the_prayer_on_the_tablet_completes_the_day(self, _now):
        self.client.force_login(self.kid)
        url = reverse("display:toggle", args=[self.lina.pk, self.prayer.pk])
        self.assertContains(self.htmx_post(url, {"done": "on"}), "Journée terminée !")
        self.assertTrue(DayStar.objects.filter(person=self.lina, date=DAY).exists())


class ZoneBTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")

    def test_prefill_is_idempotent(self):
        first = add_zone_b(self.family)
        self.assertGreater(first, 0)
        self.assertEqual(add_zone_b(self.family), 0)

    def test_parent_page_and_prefill(self):
        self.client.force_login(self.parent)
        self.assertEqual(self.get(reverse("holidays:manage")).status_code, 200)
        self.post(reverse("holidays:prefill"))
        self.assertTrue(SchoolHoliday.objects.filter(family=self.family).exists())

    def test_child_cannot_manage(self):
        self.client.force_login(self.kid)
        self.post(reverse("holidays:prefill"))
        self.assertFalse(SchoolHoliday.objects.exists())

    def test_other_family_cannot_delete(self):
        add_zone_b(self.family)
        holiday = SchoolHoliday.objects.first()
        other = make_family()
        self.client.force_login(join(other, "Alex"))
        self.assertEqual(self.post(reverse("holidays:delete", args=[holiday.pk])).status_code, 404)
