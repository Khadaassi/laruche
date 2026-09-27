import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from apps.tasks.periods import Period, current_period, period_at, seconds_until_next_period

PARIS = ZoneInfo("Europe/Paris")


def at(hour, minute=0, day=15):
    return datetime.datetime(2026, 9, day, hour, minute, tzinfo=PARIS)


class PeriodAtTests(SimpleTestCase):
    def test_boundaries(self):
        cases = [
            (datetime.time(0, 0), Period.EVENING),
            (datetime.time(3, 59), Period.EVENING),
            (datetime.time(4, 0), Period.MORNING),
            (datetime.time(10, 59), Period.MORNING),
            (datetime.time(11, 0), Period.NOON),
            (datetime.time(16, 59), Period.NOON),
            (datetime.time(17, 0), Period.EVENING),
            (datetime.time(23, 59), Period.EVENING),
        ]
        for moment, expected in cases:
            with self.subTest(moment=moment):
                self.assertEqual(period_at(moment), expected)


class CurrentPeriodTests(SimpleTestCase):
    def test_uses_server_local_time(self):
        # 06:30 UTC = 08:30 à Paris (heure d'été) : matin, pas « soir » ni « nuit ».
        utc_moment = datetime.datetime(2026, 9, 15, 6, 30, tzinfo=datetime.UTC)
        self.assertEqual(current_period(utc_moment), Period.MORNING)

    def test_evening_in_paris_is_afternoon_in_utc(self):
        utc_moment = datetime.datetime(2026, 9, 15, 15, 30, tzinfo=datetime.UTC)  # 17:30 Paris
        self.assertEqual(current_period(utc_moment), Period.EVENING)


class SecondsUntilNextPeriodTests(SimpleTestCase):
    def test_during_morning(self):
        self.assertEqual(seconds_until_next_period(at(10, 30)), 30 * 60)

    def test_during_noon(self):
        self.assertEqual(seconds_until_next_period(at(16, 0)), 60 * 60)

    def test_evening_rolls_over_to_next_morning(self):
        self.assertEqual(seconds_until_next_period(at(23, 0)), 5 * 60 * 60)

    def test_after_midnight(self):
        self.assertEqual(seconds_until_next_period(at(1, 0)), 3 * 60 * 60)
