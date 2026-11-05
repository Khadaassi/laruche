"""Moments : saisons, vendredi, Ramadan, Aïd, anniversaires, tâches allégées, réglages."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.moments import calendar as cal
from apps.moments.models import MomentSettings, PersonBirthday
from apps.moments.selectors import moments_for, relaxed_reason
from apps.stars.services import award_day_star
from apps.tasks.models import HolidayMode, Task, TaskCompletion
from apps.tasks.periods import Period

D = datetime.date


def at(day, hour_utc=8):
    return datetime.datetime(day.year, day.month, day.day, hour_utc, 0, tzinfo=datetime.UTC)


class CalendarTests(TestCase):
    def test_seasons(self):
        self.assertEqual(cal.season_of(D(2026, 11, 5)), cal.AUTUMN)
        self.assertEqual(cal.season_of(D(2027, 1, 10)), cal.WINTER)
        self.assertEqual(cal.season_of(D(2027, 4, 2)), cal.SPRING)
        self.assertEqual(cal.season_of(D(2027, 7, 14)), cal.SUMMER)

    def test_ramadan_and_eids_1448(self):
        ramadan, number = cal.ramadan_on(D(2027, 2, 8))
        self.assertEqual(number, 1)
        self.assertEqual(ramadan.end, D(2027, 3, 8))
        self.assertEqual(cal.eid_on(D(2027, 3, 9)).name, cal.EID_FITR)
        self.assertEqual(cal.eid_on(D(2027, 5, 16)).name, cal.EID_ADHA)
        self.assertIsNone(cal.eid_on(D(2027, 5, 17)))
        self.assertEqual(cal.eid_on(D(2027, 5, 17), days=2).name, cal.EID_ADHA)

    def test_shift_moves_every_date(self):
        self.assertIsNone(cal.ramadan_on(D(2027, 2, 8), shift=1))
        self.assertEqual(cal.ramadan_on(D(2027, 2, 9), shift=1)[1], 1)


class MomentsTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person

    def test_friday_and_countdown(self):
        moments = moments_for(self.family, D(2027, 4, 30))  # vendredi, 16 jours avant l'Aïd
        self.assertTrue(moments.is_friday)
        self.assertEqual(moments.theme, "friday")
        self.assertEqual((moments.next_eid.name, moments.eid_in_days), (cal.EID_ADHA, 16))
        self.assertIsNone(moments_for(self.family, D(2027, 1, 1)).next_eid)  # trop loin

    def test_ramadan_day_has_good_deed_and_eid_countdown(self):
        moments = moments_for(self.family, D(2027, 2, 20))
        self.assertEqual(moments.theme, "ramadan")
        self.assertEqual(moments.ramadan_day, 13)
        self.assertTrue(moments.good_deed)
        self.assertEqual(moments.eid_in_days, (D(2027, 3, 9) - D(2027, 2, 20)).days)

    def test_birthdays(self):
        PersonBirthday.objects.create(person=self.lina, birth_date=D(2016, 11, 8))
        today = moments_for(self.family, D(2026, 11, 8))
        self.assertEqual(today.birthdays_today, [(self.lina, 10)])
        soon = moments_for(self.family, D(2026, 11, 5))
        self.assertEqual(
            [(p, d, n, a) for p, d, n, a in soon.birthdays_soon],
            [(self.lina, D(2026, 11, 8), 3, 10)],
        )

    def test_relaxed_days(self):
        self.assertEqual(relaxed_reason(self.family, D(2027, 3, 9)), "eid")
        self.assertEqual(relaxed_reason(self.family, D(2027, 2, 20)), "ramadan")
        MomentSettings.objects.create(family=self.family, ramadan_light=False)
        self.assertEqual(relaxed_reason(self.family, D(2027, 2, 20)), "")
        self.assertEqual(relaxed_reason(self.family, D(2026, 11, 5)), "")

    def test_on_eid_only_required_tasks_give_the_star(self):
        prayer = Task.objects.create(
            person=self.lina,
            title="Prière",
            period=Period.EVENING,
            holiday_mode=HolidayMode.REQUIRED,
        )
        Task.objects.create(person=self.lina, title="Ranger", period=Period.EVENING)
        eid = D(2027, 3, 9)
        TaskCompletion.objects.create(task=prayer, date=eid)
        with mock.patch("django.utils.timezone.now", return_value=at(eid, 18)):
            self.assertTrue(award_day_star(self.lina, eid))

    def test_tablet_banners(self):
        PersonBirthday.objects.create(person=self.lina, birth_date=D(2017, 3, 9))
        with mock.patch("django.utils.timezone.now", return_value=at(D(2027, 3, 9))):
            self.client.force_login(self.kid)
            board = self.get(reverse("display:board"))
        self.assertContains(board, "Aïd Moubarak !")
        self.assertContains(board, "Joyeux anniversaire Lina !")
        self.assertContains(board, 'data-moment="eid"')
        with mock.patch("django.utils.timezone.now", return_value=at(D(2027, 2, 12))):
            self.client.force_login(self.kid)
            board = self.get(reverse("display:board"))
        self.assertContains(board, "Ramadan Moubarak · jour 5")
        self.assertContains(board, "Bonne action du jour")

    def test_parent_home_friday_and_season(self):
        with mock.patch("django.utils.timezone.now", return_value=at(D(2026, 11, 6))):
            self.client.force_login(self.parent)
            home = self.get(reverse("tasks:home"))
        self.assertContains(home, "Joumou'a Moubarak")
        self.assertContains(home, 'data-season="autumn"')

    def test_settings_page(self):
        self.client.force_login(self.parent)
        url = reverse("moments:manage")
        self.assertContains(self.get(url), "Ramadan et Aïd")
        response = self.post(
            url,
            {
                "hijri_shift": "1",
                "eid_days": "2",
                "ramadan_light": "on",
                f"naissance-{self.lina.pk}": "2016-11-08",
            },
        )
        self.assertEqual(response.status_code, 302)
        settings = MomentSettings.objects.get(family=self.family)
        self.assertEqual((settings.hijri_shift, settings.eid_days), (1, 2))
        self.assertEqual(PersonBirthday.objects.get(person=self.lina).birth_date, D(2016, 11, 8))
        bad = self.post(
            url, {"hijri_shift": "0", "eid_days": "1", f"naissance-{self.lina.pk}": "2999-01-01"}
        )
        self.assertEqual(bad.status_code, 400)

    def test_children_cannot_change_settings(self):
        self.client.force_login(self.kid)
        self.post(reverse("moments:manage"), {"hijri_shift": "1", "eid_days": "1"})
        self.assertFalse(MomentSettings.objects.exists())
