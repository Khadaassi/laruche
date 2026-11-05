"""Ménage FlyLady : programme du jour, coches partagées, réglages, isolation par famille."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.flylady.models import FlyCheck, FlyMission, FlyRoutineItem, FlyZone, RoutineKind
from apps.flylady.selectors import FLING, HOTSPOT, fly_day, zone_number_for
from apps.flylady.services import ensure_defaults

# Mercredi 18 novembre 2026 (semaine du lundi 16 → 3e semaine → zone 3).
DAY = datetime.date(2026, 11, 18)
NOON = datetime.datetime(2026, 11, 18, 11, 0, tzinfo=datetime.UTC)


class ZoneTests(TestCase):
    def test_zone_follows_the_week_of_the_month(self):
        d = datetime.date
        self.assertEqual(zone_number_for(d(2026, 11, 2)), 1)  # lundi 2
        self.assertEqual(zone_number_for(d(2026, 11, 8)), 1)  # dimanche de la même semaine
        self.assertEqual(zone_number_for(d(2026, 11, 18)), 3)
        self.assertEqual(zone_number_for(d(2026, 11, 30)), 5)
        self.assertEqual(zone_number_for(d(2026, 12, 1)), 5)  # semaine du lundi 30 nov.


@mock.patch("django.utils.timezone.now", return_value=NOON)
class FlyLadyTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.client.force_login(self.parent)

    def toggle(self, key, done=True):
        return self.htmx_post(
            reverse("flylady:toggle"), {"key": key, **({"done": "on"} if done else {})}
        )

    def test_defaults_are_created_once(self, _now):
        ensure_defaults(self.family)
        ensure_defaults(self.family)
        self.assertEqual(FlyZone.objects.filter(family=self.family).count(), 5)
        self.assertTrue(FlyMission.objects.filter(zone__family=self.family).exists())

    def test_today_page(self, _now):
        page = self.get(reverse("flylady:today"))
        self.assertContains(page, "Zone 3 · Salle de bain et chambres des enfants")
        self.assertContains(page, "Faire briller l&#x27;évier")
        self.assertContains(page, 'x-data="minuteur"')

    def test_daily_and_weekly_checks(self, _now):
        ensure_defaults(self.family)
        plan = fly_day(self.family, DAY)
        self.assertEqual(self.toggle(plan.mission.key).status_code, 204)
        self.toggle(HOTSPOT)
        self.toggle(FLING)
        blessing = plan.blessing[0].key
        self.toggle(blessing)
        monday = DAY - datetime.timedelta(days=2)
        self.assertTrue(FlyCheck.objects.filter(date=DAY, key=HOTSPOT).exists())
        self.assertTrue(FlyCheck.objects.filter(date=monday, key=FLING).exists())
        self.assertTrue(FlyCheck.objects.filter(date=monday, key=blessing).exists())
        plan = fly_day(self.family, DAY)
        self.assertTrue(plan.mission.done and plan.hotspot.done and plan.blessing[0].done)
        self.toggle(HOTSPOT, done=False)
        self.assertFalse(fly_day(self.family, DAY).hotspot.done)

    def test_unknown_or_foreign_keys_are_refused(self, _now):
        other = make_family()
        ensure_defaults(other)
        foreign = FlyRoutineItem.objects.filter(family=other).first()
        self.assertEqual(self.toggle(f"routine:{foreign.pk}").status_code, 404)
        self.assertEqual(self.toggle("nimporte").status_code, 404)

    def test_children_cannot_use_it(self, _now):
        self.client.force_login(self.kid)
        self.assertNotEqual(self.get(reverse("flylady:today")).status_code, 200)
        self.toggle(HOTSPOT)
        self.assertFalse(FlyCheck.objects.exists())

    def test_manage_add_rename_delete(self, _now):
        url = reverse("flylady:manage")
        self.get(url)
        self.post(
            url, {"action": "add_item", "kind": RoutineKind.EVENING, "title": "Dire bonne nuit"}
        )
        self.assertTrue(FlyRoutineItem.objects.filter(title="Dire bonne nuit").exists())
        zone = FlyZone.objects.get(family=self.family, number=2)
        self.post(url, {"action": "rename_zone", "pk": zone.pk, "title": "Cuisine et cellier"})
        zone.refresh_from_db()
        self.assertEqual(zone.name, "Cuisine et cellier")
        self.post(url, {"action": "add_mission", "pk": zone.pk, "title": "Trier les épices"})
        mission = FlyMission.objects.get(title="Trier les épices")
        self.post(url, {"action": "delete_mission", "pk": mission.pk})
        self.assertFalse(FlyMission.objects.filter(pk=mission.pk).exists())

    def test_manage_cannot_touch_another_family(self, _now):
        other = make_family()
        ensure_defaults(other)
        zone = FlyZone.objects.get(family=other, number=1)
        response = self.post(
            reverse("flylady:manage"), {"action": "rename_zone", "pk": zone.pk, "title": "Pirate"}
        )
        self.assertEqual(response.status_code, 404)
        zone.refresh_from_db()
        self.assertNotEqual(zone.name, "Pirate")
