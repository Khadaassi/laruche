"""Saisie rapide : course, rendez-vous, tâche d'enfant ; retour à la page d'origine."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.agenda.models import Event
from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.shopping.models import ShoppingItem
from apps.tasks.models import Task

NOW = datetime.datetime(2026, 11, 16, 8, 0, tzinfo=datetime.UTC)  # lundi 9 h


@mock.patch("django.utils.timezone.now", return_value=NOW)
class QuickAddTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.client.force_login(self.parent)
        self.url = reverse("core:quick_add")

    def test_button_on_parent_pages_only(self, _now):
        self.assertContains(self.get(reverse("tasks:home")), "Ajout rapide")
        self.client.force_login(self.kid)
        self.assertNotContains(self.get(reverse("display:board")), "Ajout rapide")

    def test_add_shopping_item_and_come_back(self, _now):
        response = self.post(self.url, {"kind": "course", "title": "Lait", "next": "/courses/"})
        self.assertRedirects(response, "/courses/?ajoute=course", fetch_redirect_response=False)
        self.assertTrue(ShoppingItem.objects.filter(family=self.family, name="Lait").exists())

    def test_add_appointment(self, _now):
        self.post(
            self.url,
            {
                "kind": "rdv",
                "title": "Dentiste",
                "date": "2026-11-20",
                "time": "16:30",
                "person": self.kid.person.pk,
                "next": "/",
            },
        )
        event = Event.objects.get(title="Dentiste")
        self.assertEqual((event.start_date, event.end_date), (datetime.date(2026, 11, 20),) * 2)
        self.assertEqual(event.end_time, datetime.time(17, 30))
        self.assertEqual(list(event.people.all()), [self.kid.person])

    def test_add_task_for_today_only(self, _now):
        self.post(
            self.url, {"kind": "tache", "title": "Ranger le cartable", "person": self.kid.person.pk}
        )
        task = Task.objects.get(title="Ranger le cartable")
        today = datetime.date(2026, 11, 16)
        self.assertEqual(
            (task.start_date, task.end_date, task.person), (today, today, self.kid.person)
        )

    def test_refusals(self, _now):
        self.assertEqual(self.post(self.url, {"kind": "course", "title": ""}).status_code, 400)
        self.assertEqual(self.post(self.url, {"kind": "piratage", "title": "x"}).status_code, 400)
        evil = self.post(
            self.url, {"kind": "course", "title": "Pain", "next": "https://evil.example/"}
        )
        self.assertRedirects(evil, "/?ajoute=course", fetch_redirect_response=False)
        other = make_family()
        stranger = join(other, "Alex")
        stranger_kid = join(other, "Zoé")
        response = self.post(
            self.url, {"kind": "tache", "title": "x", "person": stranger_kid.person.pk}
        )
        self.assertEqual(response.status_code, 404)
        self.client.force_login(self.kid)
        self.post(self.url, {"kind": "course", "title": "Bonbons"})
        self.assertFalse(ShoppingItem.objects.filter(name="Bonbons").exists())
        del stranger
