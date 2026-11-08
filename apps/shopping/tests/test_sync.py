"""Courses hors connexion : synchronisation des cochages faits en magasin."""

import datetime
import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.shopping.models import ShoppingItem, Status

URL = reverse("shopping:sync")


class SyncTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Khadija")
        self.kid = join(self.family, "Aliyah")
        self.milk = ShoppingItem.objects.create(family=self.family, name="Lait")
        self.bread = ShoppingItem.objects.create(family=self.family, name="Pain")
        self.client.force_login(self.parent)

    def send(self, *changes, user=None):
        return self.client.post(
            URL,
            data=json.dumps({"changes": list(changes)}),
            content_type="application/json",
            secure=True,
        )

    @staticmethod
    def at(minutes_ago=0):
        return (timezone.now() - datetime.timedelta(minutes=minutes_ago)).isoformat()

    def test_offline_checks_are_applied_and_states_returned(self):
        response = self.send(
            {"id": self.milk.pk, "done": True, "at": self.at(10)},
            {"id": self.bread.pk, "done": True, "at": self.at(9)},
            {"id": self.bread.pk, "done": False, "at": self.at(8)},  # décoché ensuite
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["applied"], 2)
        self.assertEqual(data["items"], {str(self.milk.pk): True, str(self.bread.pk): False})
        self.assertTrue(data["csrf"])
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.status, Status.BOUGHT)

    def test_most_recent_change_wins_between_phones(self):
        # L'autre parent décoche le lait en ligne ; ce téléphone l'avait coché avant, hors ligne.
        self.milk.set_status(Status.TO_BUY)
        response = self.send({"id": self.milk.pk, "done": True, "at": self.at(5)})
        self.assertEqual(response.json()["ignored"], 1)
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.status, Status.TO_BUY)

    def test_future_clock_is_clamped(self):
        future = (timezone.now() + datetime.timedelta(days=1)).isoformat()
        self.send({"id": self.milk.pk, "done": True, "at": future})
        self.milk.refresh_from_db()
        self.assertLessEqual(self.milk.status_changed_at, timezone.now())

    def test_other_family_deleted_and_at_home_items_are_ignored(self):
        other = ShoppingItem.objects.create(family=make_family(), name="Café")
        home = ShoppingItem.objects.create(family=self.family, name="Riz", status=Status.AT_HOME)
        response = self.send(
            {"id": other.pk, "done": True, "at": self.at()},
            {"id": home.pk, "done": True, "at": self.at()},
            {"id": 999999, "done": True, "at": self.at()},
            {"id": "x", "done": True, "at": self.at()},
            {"id": self.milk.pk, "done": "oui", "at": self.at()},
        )
        self.assertEqual(response.json()["applied"], 0)
        other.refresh_from_db()
        home.refresh_from_db()
        self.assertEqual((other.status, home.status), (Status.TO_BUY, Status.AT_HOME))
        self.assertNotIn(str(other.pk), response.json()["items"])
        self.assertNotIn(str(home.pk), response.json()["items"])

    def test_invalid_payload_and_access(self):
        bad = self.client.post(
            URL, data="pas du json", content_type="application/json", secure=True
        )
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.get(URL).status_code, 200)
        self.client.force_login(self.kid)
        self.assertNotEqual(
            self.send({"id": self.milk.pk, "done": True, "at": self.at()}).status_code, 200
        )
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.status, Status.TO_BUY)

    def test_store_page_is_ready_for_offline_use(self):
        page = self.get(reverse("shopping:store")).content.decode()
        self.assertIn('x-data="storeSync"', page)
        self.assertIn(f'data-item="{self.milk.pk}"', page)
        self.assertNotIn("hx-post", page)  # cochage géré par storeSync, pas par HTMX

    def test_service_worker_keeps_only_the_store_page(self):
        script = self.get("/sw.js").content.decode()
        self.assertIn(f"const STORE_URL = '{reverse('shopping:store')}'", script)
        self.assertIn("caches.delete(PRIVATE)", script)
