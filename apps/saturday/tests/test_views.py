import datetime
import re
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family
from apps.saturday.models import Place, PlanStatus, SaturdayActivity, SaturdayPlan
from apps.stars.tests.test_stars import earn

from .test_draw import activity

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
SATURDAY_8AM = datetime.datetime(2026, 10, 3, 6, 0, tzinfo=datetime.UTC)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class SaturdayViewsTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.games = activity(self.family, "Jeux de société", place=Place.HOME)
        self.park = activity(self.family, "Parc")
        other = make_family(name="Voisins")
        self.stranger_activity = activity(other, "Intrus")
        self.stranger_plan = SaturdayPlan.objects.create(
            family=other, date=datetime.date(2026, 10, 3), activity=self.stranger_activity
        )

    def spin(self, cost="any", place="any"):
        return self.htmx_post(reverse("saturday:spin"), {"cost": cost, "place": place})

    def test_page_header_has_no_stray_star_badge(self, _now):
        # Régression : l'en-tête affichait la liste brute des soldes (`stars`).
        self.client.force_login(self.parent)
        response = self.get(reverse("saturday:page"))
        self.assertNotContains(response, "StarBalance")
        self.assertNotContains(response, "étoiles dans la famille")

    def test_spin_returns_wheel_and_result(self, _now):
        self.client.force_login(self.parent)
        response = self.spin()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'x-data="wheel"')
        self.assertContains(response, "data-rotation=")
        self.assertContains(response, "On y va !")
        self.assertContains(response, "Retourne (2 relances restantes)")
        self.assertNotContains(response, "Intrus")

    def test_wheel_rotation_is_machine_readable(self, _now):
        # Locale française : un float s'afficherait « 1912,5 » et le JS lirait NaN,
        # la roue s'arrêterait alors à 0° au lieu de l'activité tirée.
        self.client.force_login(self.parent)
        html = self.spin().content.decode()
        raw = re.search(r'data-rotation="([^"]+)"', html).group(1)
        self.assertRegex(raw, r"^\d+(\.\d+)?$")
        self.assertGreaterEqual(float(raw), 5 * 360)

    def test_third_reroll_is_blocked_with_a_clear_message(self, _now):
        self.client.force_login(self.parent)
        self.spin()
        self.spin()
        last = self.spin()
        self.assertContains(last, "Plus de relance pour ce samedi")
        self.assertNotContains(last, "Retourne (")
        blocked = self.spin()
        self.assertEqual(blocked.status_code, 422)
        self.assertContains(blocked, "Plus de relance", status_code=422)
        self.assertEqual(SaturdayPlan.objects.get(family=self.family).spins, 3)

    def test_validate_then_visible_on_home_and_shared_screen(self, _now):
        self.client.force_login(self.parent)
        self.spin(place="home")
        plan = SaturdayPlan.objects.get(family=self.family)
        self.post(reverse("saturday:validate", args=[plan.pk]))
        plan.refresh_from_db()
        self.assertEqual(plan.status, PlanStatus.PLANNED)
        self.assertContains(self.get(reverse("tasks:home")), "Jeux de société")
        self.client.force_login(self.kid)
        board = self.get(reverse("display:board"))
        self.assertContains(board, "Jeux de société")
        self.assertNotContains(board, reverse("saturday:spin"))

    def test_mark_done_updates_history_and_last_done(self, _now):
        self.client.force_login(self.parent)
        self.spin(place="home")
        plan = SaturdayPlan.objects.get(family=self.family)
        self.post(reverse("saturday:validate", args=[plan.pk]))
        self.post(reverse("saturday:done", args=[plan.pk]))
        plan.refresh_from_db()
        self.games.refresh_from_db()
        self.assertEqual(plan.status, PlanStatus.DONE)
        self.assertEqual(self.games.last_done_on, datetime.date(2026, 9, 28))

    def test_star_activity_refused_without_enough_stars(self, _now):
        SaturdayActivity.objects.for_family(self.family).delete()
        activity(self.family, "Cirque", is_free=False, stars=10)
        self.client.force_login(self.parent)
        response = self.spin(cost="stars")
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Aucune activité", status_code=422)

    def test_star_activity_paid_on_validation(self, _now):
        lina = self.kid.person
        earn(lina, 12)
        SaturdayActivity.objects.for_family(self.family).delete()
        activity(self.family, "Cirque", is_free=False, stars=10)
        self.client.force_login(self.parent)
        self.spin(cost="stars")
        plan = SaturdayPlan.objects.get(family=self.family)
        self.post(reverse("saturday:validate", args=[plan.pk]))
        page = self.get(reverse("saturday:page"))
        self.assertContains(page, "Pot commun : 2 étoiles")
        self.assertContains(page, "Lina 10")

    def test_child_account_cannot_launch_or_manage(self, _now):
        self.client.force_login(self.kid)
        self.assertEqual(self.get(reverse("saturday:page")).status_code, 403)
        self.assertEqual(self.spin().status_code, 403)
        self.assertEqual(self.get(reverse("saturday:catalog")).status_code, 403)
        edit = reverse("saturday:edit_activity", args=[self.games.pk])
        self.assertEqual(self.post(edit, {"name": "X"}).status_code, 403)
        self.assertEqual(
            self.post(reverse("saturday:delete_activity", args=[self.games.pk])).status_code, 403
        )
        self.assertFalse(SaturdayPlan.objects.filter(family=self.family).exists())
        self.assertTrue(SaturdayActivity.objects.filter(pk=self.games.pk).exists())

    def test_shared_device_cannot_launch(self, _now):
        self.client.force_login(self.parent)
        self.post(reverse("display:activate"), {"name": "Tablette"})
        response = self.spin()
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertFalse(SaturdayPlan.objects.filter(family=self.family).exists())

    def test_other_family_plan_and_activity_are_404(self, _now):
        self.client.force_login(self.parent)
        for name in ("saturday:validate", "saturday:done", "saturday:cancel"):
            self.assertEqual(
                self.post(reverse(name, args=[self.stranger_plan.pk])).status_code, 404
            )
        edit = reverse("saturday:edit_activity", args=[self.stranger_activity.pk])
        self.assertEqual(self.get(edit).status_code, 404)
        delete = reverse("saturday:delete_activity", args=[self.stranger_activity.pk])
        self.assertEqual(self.post(delete).status_code, 404)
        self.assertTrue(SaturdayActivity.objects.filter(pk=self.stranger_activity.pk).exists())

    def test_catalog_crud(self, _now):
        self.client.force_login(self.parent)
        data = {
            "name": "Bowling",
            "season": "all",
            "place": "outing",
            "price": "15",
            "star_cost": "0",
        }
        self.post(reverse("saturday:catalog"), data)
        bowling = SaturdayActivity.objects.get(name="Bowling")
        self.assertEqual((bowling.family, bowling.is_free), (self.family, False))
        edit = reverse("saturday:edit_activity", args=[bowling.pk])
        self.post(edit, {**data, "name": "Bowling en famille", "star_cost": "20"})
        bowling.refresh_from_db()
        self.assertEqual((bowling.name, bowling.star_cost), ("Bowling en famille", 20))
        self.assertContains(
            self.get(reverse("saturday:delete_activity", args=[bowling.pk])), "Oui, supprimer"
        )
        self.post(reverse("saturday:delete_activity", args=[bowling.pk]))
        self.assertFalse(SaturdayActivity.objects.filter(pk=bowling.pk).exists())

    def test_free_activity_cannot_have_a_price(self, _now):
        self.client.force_login(self.parent)
        data = {
            "name": "X",
            "season": "all",
            "place": "home",
            "is_free": "on",
            "price": "5",
            "star_cost": "0",
        }
        self.assertEqual(self.post(reverse("saturday:catalog"), data).status_code, 400)
        self.assertFalse(SaturdayActivity.objects.filter(name="X").exists())

    def test_anonymous_redirected(self, _now):
        for url in (reverse("saturday:page"), reverse("saturday:catalog")):
            response = self.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("accounts:login"), response["Location"])


class HomeSaturdayCardTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        make_child_profile(self.family, "Lina")
        self.client.force_login(self.parent)

    def test_highlighted_on_saturday(self):
        with mock.patch("django.utils.timezone.now", return_value=SATURDAY_8AM):
            self.assertContains(self.get(reverse("tasks:home")), "C'est samedi !")

    def test_available_other_days(self):
        with mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM):
            response = self.get(reverse("tasks:home"))
        self.assertNotContains(response, "C'est samedi !")
        self.assertContains(response, "Préparer samedi")

    def test_shared_column_shows_stars_and_tier(self):
        lina = self.family.people.get(name="Lina")
        earn(lina, 13)
        with mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM):
            response = self.get(reverse("display:board"))
        self.assertContains(response, "13 étoiles")
        self.assertContains(response, "palier dans 7")
