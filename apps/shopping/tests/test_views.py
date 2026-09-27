"""Liste de courses : transfert avec aperçu, choix explicite au retransfert, permissions."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.meals.models import Meal, MealKind, MealSlot, Recipe, RecipeIngredient
from apps.shopping.models import Origin, ShoppingItem, Status

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)  # 08:00 Paris
MONDAY = datetime.date(2026, 9, 28)
TRANSFER = reverse("shopping:transfer")


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class ShoppingFlowTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.client.force_login(self.parent)
        self.couscous = self.recipe("Couscous", ("Carottes", 4, "piece"), ("Semoule", 500, "g"))
        self.tajine = self.recipe("Tajine", ("Carottes", 3, "piece"))
        self.plan(self.couscous, 0)
        self.plan(self.tajine, 2)

    def recipe(self, name, *ingredients):
        recipe = Recipe.objects.create(family=self.family, name=name)
        for ing, quantity, unit in ingredients:
            RecipeIngredient.objects.create(recipe=recipe, name=ing, quantity=quantity, unit=unit)
        return recipe

    def plan(self, recipe, offset):
        MealSlot.objects.update_or_create(
            family=self.family,
            date=MONDAY + datetime.timedelta(days=offset),
            meal=Meal.DINNER,
            defaults={"kind": MealKind.RECIPE, "recipe": recipe},
        )

    def item(self, name):
        return ShoppingItem.objects.get(name=name)

    def test_preview_writes_nothing_then_confirm_sums_quantities(self, _now):
        preview = self.get(TRANSFER)
        self.assertContains(preview, "À ajouter (2)")
        self.assertContains(preview, "Couscous · Tajine")
        self.assertFalse(ShoppingItem.objects.exists())
        self.assertRedirects(
            self.post(TRANSFER), reverse("shopping:index"), fetch_redirect_response=False
        )
        self.assertEqual(self.item("Carottes").quantity, 7)
        page = self.get(reverse("shopping:index"))
        self.assertContains(page, "Du menu de la semaine")
        self.assertContains(page, "2 articles à acheter")
        self.assertNotContains(page, "Le menu a changé")

    def test_retransfer_asks_before_touching_a_checked_item(self, _now):
        self.post(TRANSFER)
        carrots = self.item("Carottes")
        self.htmx_post(reverse("shopping:toggle", args=[carrots.pk]), {"done": "on"})
        self.assertEqual(self.item("Carottes").status, Status.BOUGHT)

        # Le menu change après coup : un 2e tajine le mercredi.
        self.plan(self.tajine, 3)
        self.assertContains(self.get(reverse("shopping:index")), "Le menu a changé")
        preview = self.get(TRANSFER)
        self.assertContains(preview, "Déjà cochés : que faire ?")
        self.assertContains(preview, "Acheté : 7 · au menu maintenant : 10")
        self.assertContains(preview, f'name="choice_{carrots.pk}" value="keep"')
        self.assertContains(preview, f'name="choice_{carrots.pk}" value="rebuy"')

        # Sans réponse : rien n'est écrit, la question est reposée.
        response = self.post(TRANSFER)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Choisissez une option", status_code=400)
        carrots.refresh_from_db()
        self.assertEqual((carrots.status, carrots.quantity), (Status.BOUGHT, 7))

        self.post(TRANSFER, {f"choice_{carrots.pk}": "rebuy"})
        carrots.refresh_from_db()
        self.assertEqual((carrots.status, carrots.quantity), (Status.TO_BUY, 10))

    def test_retransfer_keep_checked(self, _now):
        self.post(TRANSFER)
        carrots = self.item("Carottes")
        self.post(reverse("shopping:toggle", args=[carrots.pk]), {"done": "on"})
        self.plan(self.tajine, 3)
        self.post(TRANSFER, {f"choice_{carrots.pk}": "keep"})
        carrots.refresh_from_db()
        self.assertEqual((carrots.status, carrots.quantity), (Status.BOUGHT, 10))

    def test_at_home_keeps_item_out_of_active_list_and_menu_untouched(self, _now):
        self.post(TRANSFER)
        semoule = self.item("Semoule")
        self.post(reverse("shopping:at_home", args=[semoule.pk]))
        semoule.refresh_from_db()
        self.assertEqual(semoule.status, Status.AT_HOME)
        page = self.get(reverse("shopping:index"))
        self.assertNotIn(semoule, page.context["menu_items"])
        self.assertEqual(page.context["at_home_items"], [semoule])
        self.assertTrue(self.couscous.ingredients.filter(name="Semoule").exists())
        self.assertEqual(MealSlot.objects.count(), 2)
        # Transfert suivant, même menu : reste « à la maison », sans question.
        self.assertContains(self.get(TRANSFER), "La liste est déjà à jour")
        self.post(reverse("shopping:restore", args=[semoule.pk]))
        self.assertEqual(self.item("Semoule").status, Status.TO_BUY)

    def test_manual_items_add_edit_delete_and_recurring(self, _now):
        index = reverse("shopping:index")
        self.post(index, {"name": "Lait", "quantity": "2", "unit": "l", "recurring": "on"})
        self.post(index, {"name": "Piles", "quantity": "", "unit": "piece"})
        milk, batteries = self.item("Lait"), self.item("Piles")
        self.assertEqual((milk.origin, milk.recurring), (Origin.MANUAL, True))
        page = self.get(index)
        self.assertContains(page, "Habituel · chaque semaine")
        self.assertContains(page, "Ajouté à la main")
        self.assertEqual(self.post(index, {"name": ""}).status_code, 400)

        self.post(
            reverse("shopping:edit", args=[milk.pk]),
            {"name": "Lait demi-écrémé", "quantity": "3", "unit": "l", "recurring": "on"},
        )
        milk.refresh_from_db()
        self.assertEqual((milk.name, milk.quantity), ("Lait demi-écrémé", 3))

        for item in (milk, batteries):
            self.post(reverse("shopping:toggle", args=[item.pk]), {"done": "on"})
        self.post(reverse("shopping:clear"))
        self.assertEqual(self.item("Lait demi-écrémé").status, Status.TO_BUY)
        self.assertFalse(ShoppingItem.objects.filter(name="Piles").exists())

        self.post(reverse("shopping:delete", args=[milk.pk]))
        self.assertFalse(ShoppingItem.objects.filter(pk=milk.pk).exists())

    def test_menu_item_edit_has_no_recurring_option(self, _now):
        self.post(TRANSFER)
        carrots = self.item("Carottes")
        response = self.post(
            reverse("shopping:edit", args=[carrots.pk]),
            {"name": "Carottes", "quantity": "8", "unit": "piece", "recurring": "on"},
        )
        self.assertEqual(response.status_code, 302)
        carrots.refresh_from_db()
        self.assertEqual((carrots.quantity, carrots.recurring), (8, False))

    def test_toggle_is_idempotent(self, _now):
        self.post(TRANSFER)
        url = reverse("shopping:toggle", args=[self.item("Carottes").pk])
        self.assertEqual(self.htmx_post(url, {"done": "on"}).status_code, 204)
        self.htmx_post(url, {"done": "on"})
        self.assertEqual(self.item("Carottes").status, Status.BOUGHT)
        self.htmx_post(url, {})
        self.assertEqual(self.item("Carottes").status, Status.TO_BUY)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class ShoppingPermissionTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.child = join(self.family, "Lina")
        self.item = ShoppingItem.objects.create(family=self.family, name="Lait")
        other = make_family(name="Autre")
        join(other, "Max")
        self.foreign = ShoppingItem.objects.create(family=other, name="Intrus")

    def urls(self, item):
        return [
            ("post", reverse("shopping:toggle", args=[item.pk])),
            ("post", reverse("shopping:at_home", args=[item.pk])),
            ("post", reverse("shopping:restore", args=[item.pk])),
            ("get", reverse("shopping:edit", args=[item.pk])),
            ("post", reverse("shopping:edit", args=[item.pk])),
            ("post", reverse("shopping:delete", args=[item.pk])),
        ]

    def all_urls(self):
        return [
            ("get", reverse("shopping:index")),
            ("post", reverse("shopping:index")),
            ("get", TRANSFER),
            ("post", TRANSFER),
            ("post", reverse("shopping:clear")),
            *self.urls(self.item),
        ]

    def test_anonymous_is_redirected_to_login(self, _now):
        for method, url in self.all_urls():
            with self.subTest(url=url):
                response = getattr(self, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response["Location"])

    def test_child_account_has_no_access(self, _now):
        self.client.force_login(self.child)
        for method, url in self.all_urls():
            with self.subTest(url=url):
                self.assertEqual(getattr(self, method)(url, {"name": "X"}).status_code, 403)
        self.assertEqual(ShoppingItem.objects.for_family(self.family).get().name, "Lait")

    def test_shared_device_has_no_access(self, _now):
        self.client.force_login(self.parent)
        self.post(reverse("display:activate"), {"name": "Tablette"})
        for method, url in self.all_urls():
            with self.subTest(url=url):
                self.assertEqual(getattr(self, method)(url).status_code, 302)
        self.assertNotContains(self.get(reverse("display:board")), reverse("shopping:index"))

    def test_other_family_items_are_404(self, _now):
        self.client.force_login(self.parent)
        for method, url in self.urls(self.foreign):
            with self.subTest(url=url):
                self.assertEqual(getattr(self, method)(url, {"name": "Piraté"}).status_code, 404)
        self.foreign.refresh_from_db()
        self.assertEqual((self.foreign.name, self.foreign.status), ("Intrus", Status.TO_BUY))
        self.assertNotContains(self.get(reverse("shopping:index")), "Intrus")

    def test_clear_only_touches_own_family(self, _now):
        self.foreign.status = Status.BOUGHT
        self.foreign.save()
        self.client.force_login(self.parent)
        self.post(reverse("shopping:clear"))
        self.assertTrue(ShoppingItem.objects.filter(pk=self.foreign.pk).exists())
