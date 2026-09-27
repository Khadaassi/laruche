import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.celebrations.models import Celebration, CelebrationTodo, GiftItem, RecipeIdea
from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
MONDAY = datetime.date(2026, 9, 28)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class CelebrationCrudTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.lina = make_child_profile(self.family, "Lina")
        self.client.force_login(self.parent)

    def create(self, name="Aïd", date="2026-10-10"):
        self.post(reverse("celebrations:index"), {"name": name, "date": date})
        return Celebration.objects.get(name=name)

    def test_create_and_list(self, _now):
        eid = self.create()
        self.assertEqual(eid.family, self.family)
        Celebration.objects.create(
            family=self.family, name="Anniversaire passé", date=MONDAY - datetime.timedelta(days=3)
        )
        response = self.get(reverse("celebrations:index"))
        self.assertEqual([c.name for c in response.context["upcoming"]], ["Aïd"])
        self.assertEqual([c.name for c in response.context["past"]], ["Anniversaire passé"])

    def test_create_requires_name_and_date(self, _now):
        response = self.post(reverse("celebrations:index"), {"name": "", "date": ""})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Celebration.objects.exists())

    def test_edit(self, _now):
        eid = self.create()
        self.post(
            reverse("celebrations:edit", args=[eid.pk]),
            {"name": "Aïd el-Kébir", "date": "2026-10-11"},
        )
        eid.refresh_from_db()
        self.assertEqual((eid.name, eid.date), ("Aïd el-Kébir", datetime.date(2026, 10, 11)))

    def test_delete_with_confirmation(self, _now):
        eid = self.create()
        CelebrationTodo.objects.create(celebration=eid, title="Gâteaux")
        confirm = self.get(reverse("celebrations:delete", args=[eid.pk]))
        self.assertContains(confirm, "Oui, supprimer")
        self.assertTrue(Celebration.objects.exists())
        self.post(reverse("celebrations:delete", args=[eid.pk]))
        self.assertFalse(Celebration.objects.exists())
        self.assertFalse(CelebrationTodo.objects.exists())

    def test_sub_items_add_toggle_delete(self, _now):
        eid = self.create()

        def add(kind, data):
            return self.post(reverse("celebrations:add_item", args=[eid.pk, kind]), data)

        add("preparatifs", {"title": "Gâteaux", "assignee": self.parent.person.pk})
        add("cadeaux", {"item": "Vélo", "recipient": self.lina.pk, "buyer_name": "Tata Nora"})
        add("recettes", {"name": "Couscous", "notes": "Pour 12"})
        todo, gift, recipe = (
            CelebrationTodo.objects.get(),
            GiftItem.objects.get(),
            RecipeIdea.objects.get(),
        )
        self.assertEqual(todo.assignee, self.parent.person)
        self.assertEqual(gift.detail, "Pour Lina · apporté par Tata Nora")
        self.assertEqual(recipe.notes, "Pour 12")

        for kind, item in (("preparatifs", todo), ("cadeaux", gift)):
            url = reverse("celebrations:toggle_item", args=[kind, item.pk])
            self.assertEqual(self.htmx_post(url, {"done": "on"}).status_code, 204)
            item.refresh_from_db()
            self.assertTrue(item.done)
            self.htmx_post(url, {})
            item.refresh_from_db()
            self.assertFalse(item.done)
        # Une recette ne se coche pas.
        url = reverse("celebrations:toggle_item", args=["recettes", recipe.pk])
        self.assertEqual(self.htmx_post(url, {"done": "on"}).status_code, 404)

        for kind, item in (("preparatifs", todo), ("cadeaux", gift), ("recettes", recipe)):
            self.post(reverse("celebrations:delete_item", args=[kind, item.pk]))
        self.assertFalse(
            CelebrationTodo.objects.exists()
            or GiftItem.objects.exists()
            or RecipeIdea.objects.exists()
        )

    def test_detail_page(self, _now):
        eid = self.create()
        GiftItem.objects.create(celebration=eid, item="Vélo")
        response = self.get(reverse("celebrations:detail", args=[eid.pk]))
        self.assertContains(response, "Vélo")
        self.assertContains(response, "Préparatifs")


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class CelebrationPermissionTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.eid = Celebration.objects.create(
            family=self.family, name="Aïd", date=MONDAY + datetime.timedelta(days=10)
        )
        self.todo = CelebrationTodo.objects.create(celebration=self.eid, title="Gâteaux")
        self.gift = GiftItem.objects.create(
            celebration=self.eid, item="Vélo surprise", recipient=self.kid.person
        )
        RecipeIdea.objects.create(celebration=self.eid, name="Couscous")
        other = make_family(name="Voisins")
        self.stranger = make_child_profile(other, "Tom")
        self.other = Celebration.objects.create(family=other, name="Fête voisine", date=MONDAY)
        self.other_todo = CelebrationTodo.objects.create(celebration=self.other, title="Intrus")

    def test_other_family_celebration_is_404_everywhere(self, _now):
        self.client.force_login(self.parent)
        pk = self.other.pk
        self.assertEqual(self.get(reverse("celebrations:detail", args=[pk])).status_code, 404)
        self.assertEqual(
            self.post(
                reverse("celebrations:edit", args=[pk]), {"name": "X", "date": "2026-10-01"}
            ).status_code,
            404,
        )
        self.assertEqual(self.post(reverse("celebrations:delete", args=[pk])).status_code, 404)
        add = reverse("celebrations:add_item", args=[pk, "preparatifs"])
        self.assertEqual(self.post(add, {"title": "X"}).status_code, 404)
        toggle = reverse("celebrations:toggle_item", args=["preparatifs", self.other_todo.pk])
        self.assertEqual(self.htmx_post(toggle, {"done": "on"}).status_code, 404)
        delete = reverse("celebrations:delete_item", args=["preparatifs", self.other_todo.pk])
        self.assertEqual(self.post(delete).status_code, 404)
        self.other.refresh_from_db()
        self.other_todo.refresh_from_db()
        self.assertEqual(self.other.name, "Fête voisine")
        self.assertFalse(self.other_todo.done)

    def test_other_family_list_not_shown(self, _now):
        self.client.force_login(self.parent)
        self.assertNotContains(self.get(reverse("celebrations:index")), "Fête voisine")

    def test_gift_for_person_of_another_family_rejected(self, _now):
        self.client.force_login(self.parent)
        add = reverse("celebrations:add_item", args=[self.eid.pk, "cadeaux"])
        response = self.post(add, {"item": "X", "recipient": self.stranger.pk})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(GiftItem.objects.count(), 1)

    def test_child_account_cannot_edit_anything(self, _now):
        self.client.force_login(self.kid)
        pk = self.eid.pk
        self.assertEqual(self.get(reverse("celebrations:index")).status_code, 403)
        self.assertEqual(self.get(reverse("celebrations:detail", args=[pk])).status_code, 403)
        self.assertEqual(
            self.post(
                reverse("celebrations:index"), {"name": "X", "date": "2026-10-01"}
            ).status_code,
            403,
        )
        toggle = reverse("celebrations:toggle_item", args=["preparatifs", self.todo.pk])
        self.assertEqual(self.htmx_post(toggle, {"done": "on"}).status_code, 403)
        self.assertEqual(self.post(reverse("celebrations:delete", args=[pk])).status_code, 403)
        self.todo.refresh_from_db()
        self.assertFalse(self.todo.done)
        self.assertEqual(Celebration.objects.filter(family=self.family).count(), 1)

    def test_shared_screen_shows_todos_and_recipes_but_never_gifts(self, _now):
        self.client.force_login(self.kid)
        response = self.get(reverse("display:celebrations"))
        self.assertContains(response, "Aïd")
        self.assertContains(response, "Gâteaux")
        self.assertContains(response, "Couscous")
        self.assertNotContains(response, "Vélo surprise")
        self.assertNotContains(response, "Fête voisine")
        self.assertNotContains(response, "hx-post")

    def test_shared_screen_hides_past_celebrations(self, _now):
        Celebration.objects.create(
            family=self.family, name="Ancienne", date=MONDAY - datetime.timedelta(days=1)
        )
        self.client.force_login(self.parent)
        self.assertNotContains(self.get(reverse("display:celebrations")), "Ancienne")

    def test_anonymous_redirected(self, _now):
        for url in (reverse("celebrations:index"), reverse("display:celebrations")):
            response = self.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("accounts:login"), response["Location"])
