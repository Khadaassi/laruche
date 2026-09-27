"""Réglages : réservés aux parents pour tout ce qui écrit, scopés par famille."""

from django.test import TestCase
from django.urls import reverse

from apps.families.models import Person, Role

from .factories import SecureClientMixin, join, make_family


class SettingsTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family(code="RUCHECODE1")
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.other_family = make_family(name="Voisins", code="VOISINS01")
        join(self.other_family, "Paul")
        self.other_kid = join(self.other_family, "Tom")

    def test_parent_sees_invite_code(self):
        self.client.force_login(self.parent)
        self.assertContains(self.get(reverse("families:settings")), "RUCHECODE1")

    def test_child_has_no_access_to_settings(self):
        self.client.force_login(self.kid)
        self.assertEqual(self.get(reverse("families:settings")).status_code, 403)

    def test_parent_promotes_child_account(self):
        self.client.force_login(self.parent)
        self.post(reverse("families:promote", args=[self.kid.person.pk]))
        self.kid.membership.refresh_from_db()
        self.assertEqual(self.kid.membership.role, Role.PARENT)

    def test_child_cannot_promote(self):
        self.client.force_login(self.kid)
        response = self.post(reverse("families:promote", args=[self.kid.person.pk]))
        self.assertEqual(response.status_code, 403)
        self.kid.membership.refresh_from_db()
        self.assertEqual(self.kid.membership.role, Role.CHILD)

    def test_parent_cannot_promote_member_of_another_family(self):
        self.client.force_login(self.parent)
        response = self.post(reverse("families:promote", args=[self.other_kid.person.pk]))
        self.assertEqual(response.status_code, 404)
        self.other_kid.membership.refresh_from_db()
        self.assertEqual(self.other_kid.membership.role, Role.CHILD)

    def test_parent_adds_child_without_account(self):
        self.client.force_login(self.parent)
        self.post(reverse("families:add_child"), {"name": "Noah"})
        noah = Person.objects.get(name="Noah")
        self.assertEqual((noah.family, noah.role, noah.user), (self.family, Role.CHILD, None))

    def test_child_cannot_add_person(self):
        self.client.force_login(self.kid)
        self.assertEqual(self.post(reverse("families:add_child"), {"name": "X"}).status_code, 403)
        self.assertFalse(Person.objects.filter(name="X").exists())

    def test_only_parent_regenerates_code(self):
        self.client.force_login(self.kid)
        self.assertEqual(self.post(reverse("families:regenerate_code")).status_code, 403)
        self.client.force_login(self.parent)
        self.post(reverse("families:regenerate_code"))
        self.family.refresh_from_db()
        self.assertNotEqual(self.family.invite_code, "RUCHECODE1")

    def test_anonymous_redirected(self):
        response = self.get(reverse("families:settings"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
