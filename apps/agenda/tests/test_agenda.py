"""Rendez-vous : récurrence, placement dans la grille, gestion parent, lecture enfant."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.agenda.grid import events_by_day, layout_day, place
from apps.agenda.models import Event
from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)  # 08:00 Paris
MONDAY = datetime.date(2026, 9, 28)
T = datetime.time


def event(family, title="Foot", start=(14, 0), end=(15, 30), **kwargs):
    return Event.objects.create(
        family=family, title=title, start_time=T(*start), end_time=T(*end), **kwargs
    )


class GridTests(TestCase):
    def setUp(self):
        self.family = make_family()

    def test_placement_in_half_hour_rows(self):
        block = place(event(self.family, start=(14, 0), end=(15, 30)))
        # 7 h = ligne 1 ; 14 h = 14e demi-heure → ligne 15 ; 1 h 30 = 3 lignes.
        self.assertEqual((block.row_start, block.row_span, block.clipped), (15, 3, False))
        short = place(event(self.family, start=(17, 0), end=(17, 10)))
        self.assertEqual(short.row_span, 1)

    def test_out_of_range_events_are_clipped_not_lost(self):
        early = place(event(self.family, start=(6, 0), end=(8, 0)))
        self.assertEqual((early.row_start, early.row_span, early.clipped), (1, 2, True))
        late = place(event(self.family, start=(21, 30), end=(23, 0)))
        self.assertEqual((late.row_start, late.row_span, late.clipped), (30, 1, True))

    def test_overlapping_events_get_side_by_side_lanes(self):
        a = event(self.family, "A", (10, 0), (12, 0))
        b = event(self.family, "B", (10, 30), (11, 30))
        c = event(self.family, "C", (12, 0), (13, 0))  # commence quand A finit
        blocks, lanes = layout_day([a, b, c])
        self.assertEqual({blk.event.title: blk.lane for blk in blocks}, {"A": 1, "B": 2, "C": 1})
        self.assertEqual(lanes, 2)
        self.assertIn("row-start-7 row-span-4 col-start-1", blocks[0].classes)

    def test_colour_follows_the_single_person_else_family(self):
        lina = make_child_profile(self.family, "Lina")
        solo = event(self.family)
        solo.people.set([lina])
        self.assertIn(lina.avatar_classes, place(solo).classes)
        self.assertIn("bg-surface-100", place(event(self.family)).classes)

    def test_once_weekly_and_ranged_occurrences(self):
        once = event(self.family, "Dentiste", start_date=MONDAY, end_date=MONDAY)
        weekly = event(self.family, "Foot", weekdays=0b0000100)  # mercredi
        ranged = event(
            self.family,
            "Stage",
            weekdays=0b0011111,
            start_date=MONDAY + datetime.timedelta(days=3),
            end_date=MONDAY + datetime.timedelta(days=10),
        )
        days = events_by_day(self.family, MONDAY, 7)
        titles = {d.weekday(): [e.title for e in evs] for d, evs in days.items()}
        self.assertEqual(titles[0], ["Dentiste"])
        self.assertEqual(titles[2], ["Foot"])
        self.assertEqual(titles[3], ["Stage"])
        self.assertEqual(titles[5], [])
        self.assertTrue(once.is_once and not weekly.is_once and not ranged.is_once)
        other = make_family(name="Autre")
        event(other, "Intrus")
        self.assertNotIn("Intrus", str(events_by_day(self.family, MONDAY, 7)))


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class EventViewsTests(SecureClientMixin, TestCase):
    ADD = reverse("agenda:add")

    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")

    def data(self, **overrides):
        base = {
            "title": "Dentiste",
            "scope": "people",
            "people": [self.lina.pk],
            "start_time": "17:00",
            "end_time": "17:45",
            "repeat": "once",
            "date": "2026-09-30",
            "days_preset": "everyday",
            "when": "always",
            "location": "Dr Martin",
        }
        return base | overrides

    def test_create_once_and_see_it_in_the_week(self, _now):
        self.client.force_login(self.parent)
        response = self.post(self.ADD, self.data())
        self.assertEqual(response.status_code, 302)
        created = Event.objects.get()
        self.assertEqual((created.start_date, created.end_date), (datetime.date(2026, 9, 30),) * 2)
        self.assertEqual(list(created.people.all()), [self.lina])
        week = self.get(reverse("household:week"), {"jour": "2026-09-30"})
        self.assertContains(week, "Dentiste")
        self.assertContains(week, "17h00–17h45")
        self.assertEqual(week.context["selected_day"].date, datetime.date(2026, 9, 30))

    def test_create_weekly_for_the_whole_family(self, _now):
        self.client.force_login(self.parent)
        self.post(
            self.ADD,
            self.data(scope="family", people=[], repeat="weekly", days_preset="weekend", date=""),
        )
        created = Event.objects.get()
        self.assertEqual((created.weekdays, created.start_date), (0b1100000, None))
        self.assertFalse(created.people.exists())

    def test_validation(self, _now):
        self.client.force_login(self.parent)
        for bad in (
            {"end_time": "16:00"},
            {"date": ""},
            {"people": []},
            {"repeat": "weekly", "days_preset": "custom", "weekday_choices": []},
        ):
            with self.subTest(bad=bad):
                self.assertEqual(self.post(self.ADD, self.data(**bad)).status_code, 400)
        stranger = make_child_profile(make_family(name="Autre"), "Tom")
        self.assertEqual(self.post(self.ADD, self.data(people=[stranger.pk])).status_code, 400)
        self.assertFalse(Event.objects.exists())

    def test_edit_and_delete(self, _now):
        existing = event(self.family, "Foot", weekdays=0b0000100)
        self.client.force_login(self.parent)
        edit_url = reverse("agenda:edit", args=[existing.pk])
        self.assertContains(self.get(edit_url), "Supprimer toute la série")
        self.post(edit_url, self.data(title="Foot (match)", people=[self.noah.pk]))
        existing.refresh_from_db()
        self.assertEqual((existing.title, existing.is_once), ("Foot (match)", True))
        self.post(reverse("agenda:delete", args=[existing.pk]))
        self.assertFalse(Event.objects.exists())

    def test_permissions(self, _now):
        own = event(self.family)
        foreign = event(make_family(name="Autre"), "Intrus")
        self.assertEqual(self.get(self.ADD).status_code, 302)  # anonyme
        self.client.force_login(join(self.family, "Lina"))  # compte enfant
        for url in (self.ADD, reverse("agenda:edit", args=[own.pk])):
            self.assertEqual(self.post(url, self.data()).status_code, 403)
        self.assertEqual(self.post(reverse("agenda:delete", args=[own.pk])).status_code, 403)
        # L'enfant voit la grille en lecture seule, sans lien de modification.
        shared = self.get(reverse("display:week"))
        self.assertContains(shared, "Foot")
        self.assertNotContains(shared, reverse("agenda:edit", args=[own.pk]))
        self.client.force_login(self.parent)
        for url in (
            reverse("agenda:edit", args=[foreign.pk]),
            reverse("agenda:delete", args=[foreign.pk]),
        ):
            self.assertEqual(self.post(url, self.data()).status_code, 404)
        self.assertNotContains(self.get(reverse("household:week")), "Intrus")
        self.assertEqual(Event.objects.count(), 2)
