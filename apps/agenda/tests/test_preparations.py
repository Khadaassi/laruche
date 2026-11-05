"""Préparatifs des rendez-vous, accompagnateur, « Je m'en occupe »."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.agenda.models import Event, EventOccurrence, EventPrep, EventPrepCheck
from apps.agenda.preparation import upcoming
from apps.families.services import promote_to_parent
from apps.families.tests.factories import SecureClientMixin, join, make_family

TODAY = datetime.date(2026, 11, 16)  # lundi
TOMORROW = TODAY + datetime.timedelta(days=1)
NOW = datetime.datetime(2026, 11, 16, 8, 0, tzinfo=datetime.UTC)


@mock.patch("django.utils.timezone.now", return_value=NOW)
class PreparationTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.me = join(self.family, "Khadija")
        self.partner = join(self.family, "Lhousseine")
        promote_to_parent(self.partner.membership)
        self.kid = join(self.family, "Aliyah")
        self.pool = Event.objects.create(
            family=self.family,
            title="Piscine",
            start_time=datetime.time(17, 30),
            end_time=datetime.time(18, 30),
            weekdays=1 << TOMORROW.weekday(),
            driver=self.partner.person,
        )
        self.pool.people.set([self.kid.person])
        self.bag = EventPrep.objects.create(event=self.pool, title="Sac de piscine")
        self.client.force_login(self.me)

    def test_upcoming_lists_tomorrow_with_driver_and_preps(self, _now):
        [occ] = upcoming(self.family, TODAY)
        self.assertEqual((occ.date, occ.driver, occ.remaining), (TOMORROW, self.partner.person, 1))

    def test_home_card_tick_and_take_over(self, _now):
        home = self.get(reverse("tasks:home"))
        self.assertContains(home, "Rendez-vous à préparer")
        self.assertContains(home, "Sac de piscine")
        url = reverse("agenda:prep_toggle", args=[self.bag.pk])
        self.htmx_post(url, {"done": "on", "date": TOMORROW.isoformat()})
        self.assertTrue(EventPrepCheck.objects.filter(prep=self.bag, date=TOMORROW).exists())
        self.post(reverse("agenda:take_over", args=[self.pool.pk]), {"date": TOMORROW.isoformat()})
        occurrence = EventOccurrence.objects.get(event=self.pool, date=TOMORROW)
        self.assertEqual(occurrence.driver, self.me.person)
        [occ] = upcoming(self.family, TODAY)
        self.assertTrue(occ.taken_over)
        # Le réglage habituel ne change pas : seulement ce jour-là.
        self.pool.refresh_from_db()
        self.assertEqual(self.pool.driver, self.partner.person)

    def test_wrong_dates_and_other_families_refused(self, _now):
        url = reverse("agenda:prep_toggle", args=[self.bag.pk])
        self.assertEqual(
            self.htmx_post(url, {"done": "on", "date": TODAY.isoformat()}).status_code, 404
        )
        far = TOMORROW + datetime.timedelta(days=14)
        self.assertEqual(
            self.htmx_post(url, {"done": "on", "date": far.isoformat()}).status_code, 404
        )
        other = make_family()
        self.client.force_login(join(other, "Alex"))
        self.assertEqual(
            self.htmx_post(url, {"done": "on", "date": TOMORROW.isoformat()}).status_code, 404
        )

    def test_children_cannot_tick_but_see_it_on_the_tablet(self, _now):
        self.client.force_login(self.kid)
        url = reverse("agenda:prep_toggle", args=[self.bag.pk])
        self.htmx_post(url, {"done": "on", "date": TOMORROW.isoformat()})
        self.assertFalse(EventPrepCheck.objects.exists())
        self.assertContains(self.get(reverse("display:board")), "Demain Piscine : sac de piscine")

    def test_form_keeps_checked_preps_when_editing(self, _now):
        EventPrepCheck.objects.create(prep=self.bag, date=TOMORROW)
        url = reverse("agenda:edit", args=[self.pool.pk])
        page = self.get(url)
        self.assertContains(page, "Sac de piscine")
        data = {
            "title": "Piscine",
            "scope": "people",
            "people": [self.kid.person.pk],
            "start_time": "17:30",
            "end_time": "18:30",
            "repeat": "weekly",
            "days_preset": "custom",
            "weekday_choices": [str(TOMORROW.weekday())],
            "when": "always",
            "location": "",
            "driver": self.partner.person.pk,
            "preps_text": "Sac de piscine\nBonnet",
        }
        self.post(url, data)
        self.assertEqual(
            list(self.pool.preps.values_list("title", flat=True)), ["Sac de piscine", "Bonnet"]
        )
        self.assertTrue(EventPrepCheck.objects.filter(prep=self.bag).exists())
