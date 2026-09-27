"""Accueil parent et cochage : périmètre famille et rôle enfant."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family
from apps.tasks.models import Task, TaskCompletion, weekdays_to_mask
from apps.tasks.periods import Period

# Lundi 28 septembre 2026, 08:00 à Paris (06:00 UTC) : période « matin ».
MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
MONDAY = datetime.date(2026, 9, 28)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class HomeTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family(name="Les Martin")
        self.parent = join(self.family, "Sam")
        self.lina = make_child_profile(self.family, "Lina")
        self.teeth = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        Task.objects.create(person=self.lina, title="Table", period=Period.NOON)
        Task.objects.create(person=self.parent.person, title="Café", period=Period.MORNING)
        self.client.force_login(self.parent)

    def test_shows_remaining_count_not_percentage(self, _now):
        TaskCompletion.objects.create(task=self.teeth, date=MONDAY)
        response = self.get(reverse("tasks:home"))
        self.assertContains(response, "2 tâches restantes")
        self.assertNotContains(response, "%")

    def test_current_period_open_others_collapsed(self, _now):
        response = self.get(reverse("tasks:home"))
        groups = response.context["groups"]
        self.assertEqual([g.is_current for g in groups], [True, False, False])
        self.assertEqual(response.content.decode().count("open>"), 1)

    def test_filter_by_person(self, _now):
        response = self.get(reverse("tasks:home"), {"personne": self.lina.pk})
        self.assertContains(response, "Dents")
        self.assertNotContains(response, "Café")

    def test_person_of_another_family_is_404(self, _now):
        stranger = make_child_profile(make_family(name="Voisins"), "Tom")
        response = self.get(reverse("tasks:home"), {"personne": stranger.pk})
        self.assertEqual(response.status_code, 404)

    def test_invalid_person_param_is_404(self, _now):
        self.assertEqual(self.get(reverse("tasks:home"), {"personne": "abc"}).status_code, 404)

    def test_other_family_tasks_not_listed(self, _now):
        other = make_family(name="Voisins")
        Task.objects.create(
            person=make_child_profile(other, "Tom"), title="Intrus", period=Period.MORNING
        )
        self.assertNotContains(self.get(reverse("tasks:home")), "Intrus")

    def test_account_without_family_gets_403(self, _now):
        from apps.families.tests.factories import make_user

        self.client.force_login(make_user())
        self.assertEqual(self.get(reverse("tasks:home")).status_code, 403)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class ToggleTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")  # compte enfant (2e inscrit)
        self.sibling = make_child_profile(self.family, "Noah")
        self.own_task = Task.objects.create(
            person=self.kid.person, title="Dents", period=Period.MORNING
        )
        self.sibling_task = Task.objects.create(
            person=self.sibling, title="Lit", period=Period.MORNING
        )
        self.other_task = Task.objects.create(
            person=make_child_profile(make_family(name="Voisins"), "Tom"),
            title="Intrus",
            period=Period.MORNING,
        )

    def toggle(self, task, done=True, **extra):
        data = {"done": "on"} if done else {}
        data.update(extra)
        return self.htmx_post(reverse("tasks:toggle", args=[task.pk]), data)

    def test_parent_can_toggle_any_family_task(self, _now):
        self.client.force_login(self.parent)
        response = self.toggle(self.sibling_task)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TaskCompletion.objects.filter(task=self.sibling_task, date=MONDAY).exists())
        self.toggle(self.sibling_task, done=False)
        self.assertFalse(TaskCompletion.objects.filter(task=self.sibling_task).exists())

    def test_htmx_response_updates_counters_out_of_band(self, _now):
        self.client.force_login(self.parent)
        response = self.toggle(self.own_task)
        self.assertContains(response, 'id="remaining-total" hx-swap-oob="true"')
        self.assertContains(response, 'id="remaining-morning" hx-swap-oob="true"')
        self.assertContains(response, "1 tâche restante")

    def test_other_family_task_is_404(self, _now):
        self.client.force_login(self.parent)
        self.assertEqual(self.toggle(self.other_task).status_code, 404)
        self.assertFalse(TaskCompletion.objects.exists())

    def test_child_account_cannot_use_parent_toggle(self, _now):
        # Un enfant coche depuis l'écran partagé, jamais par l'accueil parent.
        self.client.force_login(self.kid)
        self.assertEqual(self.toggle(self.own_task).status_code, 403)
        self.assertFalse(TaskCompletion.objects.exists())

    def test_task_not_scheduled_today_is_404(self, _now):
        weekend = Task.objects.create(
            person=self.kid.person,
            title="Marché",
            period=Period.MORNING,
            weekdays=weekdays_to_mask([5, 6]),
        )
        self.client.force_login(self.parent)
        self.assertEqual(self.toggle(weekend).status_code, 404)

    def test_anonymous_redirected_to_login(self, _now):
        response = self.toggle(self.own_task)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertFalse(TaskCompletion.objects.exists())

    def test_get_not_allowed(self, _now):
        self.client.force_login(self.parent)
        response = self.get(reverse("tasks:toggle", args=[self.own_task.pk]))
        self.assertEqual(response.status_code, 405)

    def test_counter_filter_of_another_family_is_404(self, _now):
        self.client.force_login(self.parent)
        stranger = self.other_task.person
        self.assertEqual(self.toggle(self.own_task, personne=stranger.pk).status_code, 404)

    def test_child_account_home_redirects_to_shared_display(self, _now):
        self.client.force_login(self.kid)
        response = self.get(reverse("tasks:home"))
        self.assertRedirects(response, reverse("display:board"), fetch_redirect_response=False)


class ManageTasksTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        self.other_person = make_child_profile(make_family(name="Voisins"), "Tom")

    def task_data(self, person, **overrides):
        data = {
            "person": person.pk,
            "title": "Ranger la chambre",
            "period": Period.EVENING,
            "weekday_choices": ["0", "2", "4"],
        }
        data.update(overrides)
        return data

    def test_parent_creates_task(self):
        self.client.force_login(self.parent)
        response = self.post(reverse("tasks:manage"), self.task_data(self.lina))
        self.assertRedirects(response, reverse("tasks:manage"), fetch_redirect_response=False)
        task = Task.objects.get()
        self.assertEqual(task.weekday_list, [0, 2, 4])
        self.assertEqual(task.person, self.lina)

    def test_cannot_create_task_for_another_family_person(self):
        self.client.force_login(self.parent)
        response = self.post(reverse("tasks:manage"), self.task_data(self.other_person))
        self.assertEqual(response.status_code, 200)
        self.assertIn("person", response.context["form"].errors)
        self.assertFalse(Task.objects.exists())

    def test_at_least_one_weekday(self):
        self.client.force_login(self.parent)
        response = self.post(reverse("tasks:manage"), self.task_data(self.lina, weekday_choices=[]))
        self.assertIn("weekday_choices", response.context["form"].errors)

    def test_child_cannot_manage_tasks(self):
        self.client.force_login(self.kid)
        self.assertEqual(self.get(reverse("tasks:manage")).status_code, 403)
        response = self.post(reverse("tasks:manage"), self.task_data(self.lina))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Task.objects.exists())

    def test_child_cannot_delete_even_own_task(self):
        task = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.client.force_login(self.kid)
        self.assertEqual(self.post(reverse("tasks:delete", args=[task.pk])).status_code, 403)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_parent_cannot_delete_other_family_task(self):
        task = Task.objects.create(person=self.other_person, title="X", period=Period.MORNING)
        self.client.force_login(self.parent)
        self.assertEqual(self.post(reverse("tasks:delete", args=[task.pk])).status_code, 404)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_parent_deletes_own_family_task(self):
        task = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.client.force_login(self.parent)
        self.post(reverse("tasks:delete", args=[task.pk]))
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())


class WarmHeaderTests(SecureClientMixin, TestCase):
    """En-tête de l'accueil : salutation selon la période, étoiles de la famille."""

    def setUp(self):
        self.family = make_family(name="Famille Martin")
        self.parent = join(self.family, "Sam")
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.client.force_login(self.parent)

    def home_at(self, hour_utc):
        moment = datetime.datetime(2026, 9, 28, hour_utc, 0, tzinfo=datetime.UTC)
        with mock.patch("django.utils.timezone.now", return_value=moment):
            return self.get(reverse("tasks:home"))

    def test_greeting_follows_the_period(self):
        # Heure de Paris = UTC + 2 en septembre.
        self.assertContains(self.home_at(6), "Bonjour la famille")  # 08:00
        self.assertContains(self.home_at(12), "Bon après-midi")  # 14:00
        self.assertContains(self.home_at(18), "Bonsoir la famille")  # 20:00

    def test_family_name_and_date_stay_visible(self):
        response = self.home_at(6)
        self.assertContains(response, "Famille Martin · Lundi 28 septembre")
        self.assertContains(response, "tâche restante")

    def test_star_pill_sums_children_stars(self):
        from apps.stars.tests.test_stars import earn

        earn(self.lina, 7, start=MONDAY - datetime.timedelta(days=1))
        earn(self.noah, 5, start=MONDAY - datetime.timedelta(days=1))
        # Les parents ne gagnent pas d'étoiles : ne compte pas.
        earn(self.parent.person, 9, start=MONDAY - datetime.timedelta(days=1))
        response = self.home_at(6)
        self.assertEqual(response.context["family_stars"], 12)
        self.assertContains(response, '12<span class="sr-only"> étoiles dans la famille</span>')

    def test_tasks_are_mini_cards(self):
        html = self.home_at(6).content.decode()
        self.assertIn("rounded-md border border-border bg-surface-100", html)
        self.assertNotIn("divide-y divide-border border-t border-border px-space-4", html)
