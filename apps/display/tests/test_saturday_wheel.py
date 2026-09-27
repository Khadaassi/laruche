"""Roue du samedi lancée depuis l'écran partagé, après confirmation d'un parent."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.display.models import SharedDisplayDevice
from apps.families.tests.factories import PASSWORD, SecureClientMixin, join, make_family
from apps.saturday.models import Place, PlanStatus, SaturdayPlan
from apps.saturday.tests.test_draw import activity

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class TabletWheelTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        activity(self.family, "Jeux de société", place=Place.HOME)
        activity(self.family, "Parc")
        self.other_parent = join(make_family(name="Voisins"), "Paul")
        # L'écran est une tablette partagée activée par un parent.
        self.client.force_login(self.parent)
        self.post(reverse("display:activate"), {"name": "Tablette"})

    def unlock(self, user=None, password=PASSWORD, **extra):
        user = user or self.parent
        return self.post(
            reverse("display:saturday_unlock"),
            {"username": user.email, "password": password},
            **extra,
        )

    def spin(self):
        return self.htmx_post(reverse("display:saturday_spin"), {"cost": "any", "place": "any"})

    def test_page_asks_for_parent_password(self, _now):
        response = self.get(reverse("display:saturday"))
        self.assertContains(response, "Un parent confirme avec son mot de passe")
        self.assertNotContains(response, "Tourner la roue")

    def test_cannot_spin_without_confirmation(self, _now):
        self.assertEqual(self.spin().status_code, 403)
        self.assertFalse(SaturdayPlan.objects.exists())

    def test_parent_password_unlocks_the_wheel_on_the_shared_screen(self, _now):
        response = self.unlock()
        self.assertRedirects(response, reverse("display:saturday"), fetch_redirect_response=False)
        # La session de l'écran n'est PAS connectée en parent.
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(self.get(reverse("display:saturday")), "Tourner la roue")
        spun = self.spin()
        self.assertEqual(spun.status_code, 200)
        self.assertContains(spun, 'x-data="wheel"')
        self.assertContains(spun, reverse("display:saturday_spin"))
        plan = SaturdayPlan.objects.get()
        self.assertEqual((plan.spins, plan.created_by), (1, self.parent))

    def test_same_three_spin_limit(self, _now):
        self.unlock()
        for _ in range(3):
            self.spin()
        blocked = self.spin()
        self.assertEqual(blocked.status_code, 422)
        self.assertContains(blocked, "Plus de relance", status_code=422)

    def test_validate_from_tablet_then_plan_on_board(self, _now):
        self.unlock()
        self.spin()
        plan = SaturdayPlan.objects.get()
        response = self.post(reverse("display:saturday_validate", args=[plan.pk]))
        self.assertRedirects(response, reverse("display:board"), fetch_redirect_response=False)
        plan.refresh_from_db()
        self.assertEqual(plan.status, PlanStatus.PLANNED)
        self.assertContains(self.get(reverse("display:board")), plan.activity_name)
        # Le déverrouillage est consommé.
        self.assertEqual(self.spin().status_code, 403)

    def test_wrong_password_is_refused(self, _now):
        response = self.unlock(password="faux")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.spin().status_code, 403)

    def test_child_or_other_family_parent_cannot_unlock(self, _now):
        self.assertContains(
            self.unlock(user=self.kid), "Seul un parent de cette famille", status_code=400
        )
        self.assertContains(
            self.unlock(user=self.other_parent), "Seul un parent de cette famille", status_code=400
        )
        self.assertEqual(self.spin().status_code, 403)

    def test_rate_limit_shared_with_tablet_exit(self, _now):
        # Même garde que la sortie du mode tablette : les échecs s'additionnent.
        for _ in range(3):
            self.post(reverse("display:exit"), {"username": self.parent.email, "password": "faux"})
        for n in range(2):
            self.unlock(password="faux", REMOTE_ADDR=f"10.0.0.{n}")
        blocked = self.unlock(REMOTE_ADDR="192.0.2.8")  # bon mot de passe, autre IP
        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "Trop de tentatives", status_code=429)
        self.assertEqual(self.spin().status_code, 403)
        self.assertTrue(SharedDisplayDevice.objects.get().is_active)

    def test_unlock_expires(self, _now):
        self.unlock()
        later = MONDAY_8AM + datetime.timedelta(minutes=11)
        with mock.patch("django.utils.timezone.now", return_value=later):
            self.assertEqual(self.spin().status_code, 403)

    def test_child_account_on_shared_screen_needs_parent_too(self, _now):
        self.client.cookies.clear()
        self.client.force_login(self.kid)
        self.assertEqual(self.spin().status_code, 403)
        self.unlock()
        self.assertEqual(self.spin().status_code, 200)

    def test_parent_preview_needs_no_password(self, _now):
        self.client.cookies.clear()
        self.client.force_login(self.parent)
        self.assertContains(self.get(reverse("display:saturday")), "Tourner la roue")
        self.assertEqual(self.spin().status_code, 200)
