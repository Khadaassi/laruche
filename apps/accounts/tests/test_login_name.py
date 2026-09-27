"""Identifiant court de connexion et compte « écran partagé » des enfants."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.families.models import FamilyMembership, Person, Role
from apps.families.services import create_display_account, set_login_name
from apps.families.tests.factories import (
    PASSWORD,
    SecureClientMixin,
    join,
    make_child_profile,
    make_family,
)
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
LOGIN = reverse("accounts:login")


class LoginNameTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Khadija")
        set_login_name(self.parent, "Khadija")

    def login(self, username, password=PASSWORD, **extra):
        return self.post(LOGIN, {"username": username, "password": password}, **extra)

    def test_identifier_is_stored_lowercase(self):
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.login_name, "khadija")

    def test_login_with_identifier_any_case(self):
        response = self.login(" KHADIJA ")
        self.assertRedirects(response, reverse("tasks:home"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.parent.pk)

    def test_login_with_email_still_works(self):
        response = self.login(self.parent.email)
        self.assertRedirects(response, reverse("tasks:home"), fetch_redirect_response=False)

    def test_wrong_password_or_unknown_identifier_give_the_same_message(self):
        for username, password in [("khadija", "faux"), ("inconnu", PASSWORD)]:
            response = self.login(username, password)
            self.assertContains(response, "Identifiant, e-mail ou mot de passe incorrect")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_identifier_and_email_share_the_rate_limit(self):
        for n in range(5):
            self.login("khadija", "faux", REMOTE_ADDR=f"10.0.0.{n}")
            self.login(self.parent.email, "faux", REMOTE_ADDR=f"10.0.1.{n}")
        response = self.login("khadija", REMOTE_ADDR="192.0.2.9")
        self.assertEqual(response.status_code, 429)

    def test_parent_confirms_with_identifier_on_the_shared_screen(self):
        kids = create_display_account(self.family, login_name="enfants", password=PASSWORD)
        self.client.force_login(kids)
        response = self.post(reverse("display:exit"), {"username": "khadija", "password": PASSWORD})
        self.assertRedirects(response, reverse("tasks:home"), fetch_redirect_response=False)


class LoginNameSettingsTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Khadija")
        self.kid = join(self.family, "Lina")
        self.client.force_login(self.parent)

    def set_name(self, user, value):
        url = reverse("families:update_login_name", args=[user.pk])
        return self.post(url, {f"account-{user.pk}-login_name": value})

    def test_parent_sets_and_removes_an_identifier(self):
        self.assertRedirects(
            self.set_name(self.kid, "Lina"),
            reverse("families:settings"),
            fetch_redirect_response=False,
        )
        self.kid.refresh_from_db()
        self.assertEqual(self.kid.login_name, "lina")
        self.set_name(self.kid, "")
        self.kid.refresh_from_db()
        self.assertIsNone(self.kid.login_name)

    def test_duplicate_or_invalid_identifier_is_refused(self):
        set_login_name(join(make_family(name="Voisins"), "Tom"), "lina")
        response = self.set_name(self.kid, "lina")
        self.assertContains(response, "déjà pris", status_code=400)
        response = self.set_name(self.kid, "éa@x")
        self.assertContains(response, "De 2 à 30 caractères", status_code=400)
        self.kid.refresh_from_db()
        self.assertIsNone(self.kid.login_name)

    def test_other_family_account_is_404(self):
        stranger = join(make_family(name="Voisins"), "Tom")
        self.assertEqual(self.set_name(stranger, "tom").status_code, 404)

    def test_child_account_cannot_set_identifiers(self):
        self.client.force_login(self.kid)
        self.assertEqual(self.set_name(self.kid, "lina").status_code, 403)

    def test_anonymous_is_redirected(self):
        self.client.logout()
        response = self.set_name(self.kid, "lina")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_settings_list_every_account(self):
        set_login_name(self.parent, "khadija")
        response = self.get(reverse("families:settings"))
        self.assertContains(response, "Comptes et identifiants")
        self.assertContains(response, 'value="khadija"')


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class DisplayAccountTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Khadija")
        self.aliyah = make_child_profile(self.family, "Aliyah")
        self.zayd = make_child_profile(self.family, "Zayd")
        self.task = Task.objects.create(person=self.zayd, title="Dents", period=Period.MORNING)

    def create(self, **data):
        self.client.force_login(self.parent)
        payload = {"login_name": "enfants", "password": PASSWORD, **data}
        return self.post(reverse("families:create_display"), payload)

    def test_parent_creates_it_without_person_or_email(self, _now):
        self.assertRedirects(
            self.create(), reverse("families:settings"), fetch_redirect_response=False
        )
        user = User.objects.get(login_name="enfants")
        self.assertEqual(user.membership.role, Role.DISPLAY)
        self.assertEqual(user.family, self.family)
        self.assertEqual(user.email, "")
        self.assertFalse(Person.objects.filter(user=user).exists())
        self.assertEqual(Person.objects.for_family(self.family).count(), 3)

    def test_only_one_per_family_and_weak_password_refused(self, _now):
        self.assertContains(self.create(password="court"), "12", status_code=400)
        self.create()
        self.create(login_name="enfants2")
        self.assertEqual(
            FamilyMembership.objects.filter(family=self.family, role=Role.DISPLAY).count(), 1
        )

    def test_child_account_cannot_create_it(self, _now):
        kid = join(self.family, "Lina")
        self.client.force_login(kid)
        response = self.post(
            reverse("families:create_display"), {"login_name": "enfants", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(login_name="enfants").exists())

    def test_login_opens_the_shared_screen_with_every_column_tickable(self, _now):
        create_display_account(self.family, login_name="enfants", password=PASSWORD)
        login = self.post(LOGIN, {"username": "enfants", "password": PASSWORD})
        self.assertRedirects(login, reverse("tasks:home"), fetch_redirect_response=False)
        # L'accueil envoie tout compte non parent sur l'écran partagé.
        self.assertRedirects(
            self.get(reverse("tasks:home")), reverse("display:board"), fetch_redirect_response=False
        )
        response = self.get(reverse("display:board"))
        self.assertContains(response, "Aliyah")
        self.assertContains(response, "Zayd")
        self.assertContains(response, "Mode parent")
        self.assertNotContains(response, "(lecture seule)")
        url = reverse("display:toggle", args=[self.zayd.pk, self.task.pk])
        self.assertEqual(self.htmx_post(url, {"done": "on"}).status_code, 200)
        self.assertTrue(TaskCompletion.objects.filter(task=self.task).exists())

    def test_no_parent_page(self, _now):
        kids = create_display_account(self.family, login_name="enfants", password=PASSWORD)
        self.client.force_login(kids)
        for name in ("families:settings", "tasks:manage", "household:week", "shopping:index"):
            self.assertEqual(self.get(reverse(name)).status_code, 403, name)

    def test_cannot_tick_another_family(self, _now):
        other = make_family(name="Voisins")
        tom = make_child_profile(other, "Tom")
        task = Task.objects.create(person=tom, title="Lit", period=Period.MORNING)
        kids = create_display_account(self.family, login_name="enfants", password=PASSWORD)
        self.client.force_login(kids)
        url = reverse("display:toggle", args=[tom.pk, task.pk])
        self.assertEqual(self.htmx_post(url, {"done": "on"}).status_code, 404)

    def test_exit_needs_a_parent_of_this_family(self, _now):
        kids = create_display_account(self.family, login_name="enfants", password=PASSWORD)
        stranger = join(make_family(name="Voisins"), "Paul")
        self.client.force_login(kids)
        response = self.post(
            reverse("display:exit"), {"username": stranger.email, "password": PASSWORD}
        )
        self.assertContains(response, "Seul un parent de cette famille")
        self.assertEqual(int(self.client.session["_auth_user_id"]), kids.pk)
        response = self.post(
            reverse("display:exit"), {"username": self.parent.email, "password": PASSWORD}
        )
        self.assertRedirects(response, reverse("tasks:home"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.parent.pk)

    def test_delete_it(self, _now):
        create_display_account(self.family, login_name="enfants", password=PASSWORD)
        self.client.force_login(self.parent)
        self.post(reverse("families:delete_display"))
        self.assertFalse(User.objects.filter(login_name="enfants").exists())
        self.assertTrue(User.objects.filter(pk=self.parent.pk).exists())
