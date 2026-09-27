"""Affichage partagé : jeton d'appareil, privilège « enfant », périmètre famille."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.display.access import DEVICE_COOKIE
from apps.display.models import SharedDisplayDevice, hash_token
from apps.families.tests.factories import (
    PASSWORD,
    SecureClientMixin,
    join,
    make_child_profile,
    make_family,
)
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)  # 08:00 Paris


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class BoardAccessTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family(name="Les Martin")
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        make_child_profile(self.family, "Noah")
        make_child_profile(self.family, "Zoé")

    def test_anonymous_redirected_to_login(self, _now):
        response = self.get(reverse("display:board"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_child_account_sees_every_child_column(self, _now):
        # Un accès enfant n'est jamais une vue mono-enfant : toutes les colonnes,
        # seule la sienne est cochable.
        self.client.force_login(self.kid)
        response = self.get(reverse("display:board"))
        self.assertEqual(response.status_code, 200)
        columns = response.context["columns"]
        self.assertEqual([c.person.name for c in columns], ["Lina", "Noah", "Zoé"])
        self.assertEqual([c.tickable for c in columns], [True, False, False])
        self.assertContains(response, "Se déconnecter")
        self.assertNotContains(response, "Retour à mon compte")

    def test_parent_preview_can_tick_every_column(self, _now):
        self.client.force_login(self.parent)
        columns = self.get(reverse("display:board")).context["columns"]
        self.assertTrue(all(c.tickable for c in columns))

    def test_account_without_family_is_refused(self, _now):
        from apps.families.tests.factories import make_user

        self.client.force_login(make_user())
        self.assertEqual(self.get(reverse("display:board")).status_code, 403)

    def test_parent_preview_shows_one_column_per_child(self, _now):
        self.client.force_login(self.parent)
        response = self.get(reverse("display:board"))
        names = [c.person.name for c in response.context["columns"]]
        self.assertEqual(names, ["Lina", "Noah", "Zoé"])  # le parent n'a pas de colonne

    def test_only_current_period_tasks(self, _now):
        lina = self.kid.person
        Task.objects.create(person=lina, title="Dents", period=Period.MORNING)
        Task.objects.create(person=lina, title="Bain", period=Period.EVENING)
        self.client.force_login(self.parent)
        response = self.get(reverse("display:board"))
        self.assertContains(response, "Dents")
        self.assertNotContains(response, "Bain")
        # Rechargement programmé au passage à midi (11:00), dans 3 h.
        self.assertContains(response, 'data-reload-in="10800"')


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class DeviceTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family(name="Les Martin")
        self.parent = join(self.family, "Sam")
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        self.lina_task = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.noah_task = Task.objects.create(person=self.noah, title="Lit", period=Period.MORNING)
        self.parent_task = Task.objects.create(
            person=self.parent.person, title="Café", period=Period.MORNING
        )
        other = make_family(name="Voisins")
        self.stranger = make_child_profile(other, "Tom")
        self.stranger_task = Task.objects.create(
            person=self.stranger, title="Intrus", period=Period.MORNING
        )

    def activate(self):
        self.client.force_login(self.parent)
        return self.post(reverse("display:activate"), {"name": "Tablette cuisine"})

    def toggle(self, person, task):
        return self.htmx_post(reverse("display:toggle", args=[person.pk, task.pk]), {"done": "on"})

    def test_activation_creates_device_and_closes_parent_session(self, _now):
        response = self.activate()
        self.assertRedirects(response, reverse("display:board"), fetch_redirect_response=False)
        device = SharedDisplayDevice.objects.get()
        raw = response.cookies[DEVICE_COOKIE].value
        self.assertEqual(device.token_hash, hash_token(raw))  # seule l'empreinte est stockée
        self.assertTrue(response.cookies[DEVICE_COOKIE]["httponly"])
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.get(reverse("display:board")).status_code, 200)

    def test_device_has_no_parent_privilege(self, _now):
        self.activate()
        for name in ("tasks:home", "families:settings", "tasks:manage"):
            with self.subTest(name=name):
                response = self.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response["Location"])
        response = self.post(reverse("tasks:toggle", args=[self.lina_task.pk]), {"done": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TaskCompletion.objects.exists())

    def test_device_toggles_child_task(self, _now):
        self.activate()
        response = self.toggle(self.lina, self.lina_task)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="child-status-{self.lina.pk}" hx-swap-oob="true"')
        completion = TaskCompletion.objects.get()
        self.assertEqual(completion.task, self.lina_task)
        self.assertIsNone(completion.completed_by)

    def test_column_cannot_touch_another_column(self, _now):
        self.activate()
        self.assertEqual(self.toggle(self.lina, self.noah_task).status_code, 404)
        self.assertFalse(TaskCompletion.objects.exists())

    def test_device_cannot_toggle_parent_task(self, _now):
        self.activate()
        self.assertEqual(self.toggle(self.parent.person, self.parent_task).status_code, 404)

    def test_device_cannot_toggle_other_family_child(self, _now):
        self.activate()
        self.assertEqual(self.toggle(self.stranger, self.stranger_task).status_code, 404)
        self.assertEqual(self.toggle(self.lina, self.stranger_task).status_code, 404)
        self.assertFalse(TaskCompletion.objects.exists())

    def test_revoked_device_loses_access(self, _now):
        self.activate()
        SharedDisplayDevice.objects.get().revoke()
        response = self.get(reverse("display:board"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.toggle(self.lina, self.lina_task).status_code, 302)

    def test_forged_cookie_has_no_access(self, _now):
        self.client.cookies[DEVICE_COOKIE] = "jeton-invente"
        self.assertEqual(self.get(reverse("display:board")).status_code, 302)

    def test_parent_revokes_device_from_settings(self, _now):
        self.activate()
        device = SharedDisplayDevice.objects.get()
        self.client.force_login(self.parent)
        self.post(reverse("display:revoke", args=[device.pk]))
        device.refresh_from_db()
        self.assertFalse(device.is_active)

    def test_other_family_parent_cannot_revoke(self, _now):
        self.activate()
        device = SharedDisplayDevice.objects.get()
        self.client.force_login(join(self.stranger.family, "Paul"))
        self.assertEqual(self.post(reverse("display:revoke", args=[device.pk])).status_code, 404)
        device.refresh_from_db()
        self.assertTrue(device.is_active)

    def test_device_can_tick_every_column(self, _now):
        self.activate()
        columns = self.get(reverse("display:board")).context["columns"]
        self.assertEqual([c.tickable for c in columns], [True, True])

    def test_child_account_cannot_activate(self, _now):
        kid = join(self.family, "Léo")
        self.client.force_login(kid)
        self.assertEqual(self.post(reverse("display:activate")).status_code, 403)
        self.assertFalse(SharedDisplayDevice.objects.exists())

    def test_exit_requires_parent_of_this_family(self, _now):
        self.activate()
        other_parent = join(self.stranger.family, "Paul")
        response = self.post(
            reverse("display:exit"), {"username": other_parent.email, "password": PASSWORD}
        )
        self.assertContains(response, "Seul un parent de cette famille")
        self.assertTrue(SharedDisplayDevice.objects.get().is_active)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_exit_attempts_are_limited_per_device(self, _now):
        self.activate()
        for n in range(5):
            self.post(
                reverse("display:exit"),
                {"username": self.parent.email, "password": "faux"},
                REMOTE_ADDR=f"10.0.0.{n}",
            )
        # Bloqué même avec le bon mot de passe et une autre IP : l'appareil reste.
        response = self.post(
            reverse("display:exit"),
            {"username": self.parent.email, "password": PASSWORD},
            REMOTE_ADDR="192.0.2.7",
        )
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Trop de tentatives", status_code=429)
        self.assertTrue(SharedDisplayDevice.objects.get().is_active)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_exit_with_parent_password_revokes_device(self, _now):
        self.activate()
        response = self.post(
            reverse("display:exit"), {"username": self.parent.email, "password": PASSWORD}
        )
        self.assertRedirects(response, reverse("tasks:home"), fetch_redirect_response=False)
        self.assertFalse(SharedDisplayDevice.objects.get().is_active)
        self.assertEqual(response.cookies[DEVICE_COOKIE].value, "")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.parent.pk)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class ChildAccountToggleTests(SecureClientMixin, TestCase):
    """Compte enfant sur l'écran partagé : coche sa colonne, pas celle des autres."""

    def setUp(self):
        self.family = make_family()
        join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        self.own_task = Task.objects.create(
            person=self.kid.person, title="Dents", period=Period.MORNING
        )
        self.sibling_task = Task.objects.create(
            person=self.noah, title="Lit", period=Period.MORNING
        )
        stranger = make_child_profile(make_family(name="Voisins"), "Tom")
        self.stranger_task = Task.objects.create(
            person=stranger, title="Intrus", period=Period.MORNING
        )
        self.client.force_login(self.kid)

    def toggle(self, task):
        return self.htmx_post(
            reverse("display:toggle", args=[task.person.pk, task.pk]), {"done": "on"}
        )

    def test_child_ticks_own_column(self, _now):
        self.assertEqual(self.toggle(self.own_task).status_code, 200)
        self.assertEqual(TaskCompletion.objects.get().completed_by, self.kid)

    def test_child_cannot_tick_sibling_column(self, _now):
        self.assertEqual(self.toggle(self.sibling_task).status_code, 403)
        self.assertFalse(TaskCompletion.objects.exists())

    def test_child_cannot_tick_other_family(self, _now):
        self.assertEqual(self.toggle(self.stranger_task).status_code, 404)
        self.assertFalse(TaskCompletion.objects.exists())

    def test_sibling_column_rendered_read_only(self, _now):
        html = self.get(reverse("display:board")).content.decode()
        self.assertIn(
            f'hx-post="{reverse("display:toggle", args=[self.kid.person.pk, self.own_task.pk])}"',
            html,
        )
        self.assertNotIn(
            f'hx-post="{reverse("display:toggle", args=[self.noah.pk, self.sibling_task.pk])}"',
            html,
        )
