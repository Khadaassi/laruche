"""Recettes et menu de la semaine : CRUD parent, lecture seule enfant, isolation."""

import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.meals.models import Meal, MealKind, MealSlot, Recipe, RecipeIngredient, RecipeStep

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)  # 08:00 Paris
MONDAY = datetime.date(2026, 9, 28)


def slot_url(day, meal):
    return reverse("meals:slot_edit", args=[day.isoformat(), meal])


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class RecipeCrudTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.client.force_login(self.parent)

    def create(self, **data):
        payload = {"name": "Couscous", "prep_minutes": "45", "steps_text": ""} | data
        response = self.post(reverse("meals:recipes"), payload)
        return response, Recipe.objects.filter(name=payload["name"]).first()

    def test_create_with_ordered_steps(self, _now):
        response, recipe = self.create(steps_text="1. Couper les légumes\n\n- Cuire 30 min\nServir")
        self.assertRedirects(
            response,
            reverse("meals:recipe_detail", args=[recipe.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual((recipe.family, recipe.prep_minutes), (self.family, 45))
        self.assertEqual(
            list(recipe.steps.values_list("position", "text")),
            [(1, "Couper les légumes"), (2, "Cuire 30 min"), (3, "Servir")],
        )
        detail = self.get(reverse("meals:recipe_detail", args=[recipe.pk]))
        self.assertContains(detail, "Couper les légumes")
        self.assertContains(detail, "Préparation : 45 min")

    def test_create_requires_a_name(self, _now):
        response, _ = self.create(name="")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Recipe.objects.exists())

    def test_list_puts_favorites_first_and_filters(self, _now):
        Recipe.objects.create(family=self.family, name="Aubergines")
        Recipe.objects.create(family=self.family, name="Tajine", is_favorite=True)
        Recipe.objects.create(family=make_family(name="Autre"), name="Intrus")
        response = self.get(reverse("meals:recipes"))
        self.assertEqual([r.name for r in response.context["recipes"]], ["Tajine", "Aubergines"])
        favorites = self.get(reverse("meals:recipes"), {"favoris": "1"})
        self.assertEqual([r.name for r in favorites.context["recipes"]], ["Tajine"])

    def test_edit_replaces_steps(self, _now):
        _, recipe = self.create(steps_text="Un\nDeux")
        self.post(
            reverse("meals:recipe_edit", args=[recipe.pk]),
            {
                "name": "Couscous royal",
                "prep_minutes": "",
                "steps_text": "Trois",
                "is_favorite": "on",
            },
        )
        recipe.refresh_from_db()
        self.assertEqual(
            (recipe.name, recipe.prep_minutes, recipe.is_favorite), ("Couscous royal", None, True)
        )
        self.assertEqual(list(recipe.steps.values_list("text", flat=True)), ["Trois"])

    def test_favorite_toggle(self, _now):
        _, recipe = self.create()
        url = reverse("meals:recipe_favorite", args=[recipe.pk])
        self.post(url, {"favorite": "on"})
        recipe.refresh_from_db()
        self.assertTrue(recipe.is_favorite)
        self.post(url)
        recipe.refresh_from_db()
        self.assertFalse(recipe.is_favorite)

    def test_ingredients_add_with_quantity_and_unit_then_delete(self, _now):
        _, recipe = self.create()
        url = reverse("meals:ingredient_add", args=[recipe.pk])
        self.post(url, {"name": "Semoule", "quantity": "0.5", "unit": "kg"})
        self.post(url, {"name": "Sel", "quantity": "", "unit": "piece"})
        semoule, sel = recipe.ingredients.all()
        self.assertEqual((semoule.quantity, semoule.unit), (Decimal("0.5"), "kg"))
        self.assertEqual(semoule.quantity_display, "0,5 kg")
        self.assertIsNone(sel.quantity)
        self.assertContains(
            self.get(reverse("meals:recipe_detail", args=[recipe.pk])), "à convenance"
        )
        self.assertEqual(
            self.post(url, {"name": "X", "quantity": "-1", "unit": "g"}).status_code, 400
        )
        self.post(reverse("meals:ingredient_delete", args=[semoule.pk]))
        self.assertEqual(list(recipe.ingredients.all()), [sel])

    def test_delete_with_confirmation_also_removes_menu_slots(self, _now):
        _, recipe = self.create(steps_text="Un")
        RecipeIngredient.objects.create(recipe=recipe, name="Semoule", quantity=500, unit="g")
        MealSlot.objects.create(
            family=self.family, date=MONDAY, meal=Meal.DINNER, kind=MealKind.RECIPE, recipe=recipe
        )
        confirm = self.get(reverse("meals:recipe_delete", args=[recipe.pk]))
        self.assertContains(confirm, "retirée du menu")
        self.post(reverse("meals:recipe_delete", args=[recipe.pk]))
        self.assertFalse(Recipe.objects.exists())
        self.assertFalse(RecipeIngredient.objects.exists() or RecipeStep.objects.exists())
        self.assertFalse(MealSlot.objects.exists())


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class MenuTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.client.force_login(self.parent)
        self.recipe = Recipe.objects.create(family=self.family, name="Couscous", prep_minutes=45)

    def test_week_view_and_navigation(self, _now):
        MealSlot.objects.create(
            family=self.family,
            date=MONDAY,
            meal=Meal.DINNER,
            kind=MealKind.RECIPE,
            recipe=self.recipe,
        )
        response = self.get(reverse("meals:menu"))
        self.assertEqual(response.context["monday"], MONDAY)
        self.assertEqual(response.context["days"][0].dinner.recipe, self.recipe)
        self.assertContains(response, "Couscous")
        self.assertContains(response, 'aria-current="page"')
        next_week = self.get(reverse("meals:menu"), {"semaine": "2026-10-07"})
        self.assertEqual(next_week.context["monday"], datetime.date(2026, 10, 5))
        self.assertEqual(self.get(reverse("meals:menu"), {"semaine": "demain"}).status_code, 404)

    def test_set_recipe_free_meal_then_clear(self, _now):
        url = slot_url(MONDAY, Meal.LUNCH)
        self.assertContains(self.get(url), "Déjeuner")
        self.post(url, {"kind": "recipe", "recipe": self.recipe.pk})
        slot = MealSlot.objects.get()
        self.assertEqual((slot.meal, slot.recipe), (Meal.LUNCH, self.recipe))
        self.post(url, {"kind": "leftovers", "recipe": self.recipe.pk, "note": "du couscous"})
        slot.refresh_from_db()
        self.assertEqual(
            (slot.kind, slot.recipe, slot.label), ("leftovers", None, "Restes · du couscous")
        )
        self.post(url, {"kind": "free", "note": "Pizza"})
        slot.refresh_from_db()
        self.assertEqual(slot.label, "Pizza")
        self.post(url, {"kind": "none"})
        self.assertFalse(MealSlot.objects.exists())

    def test_invalid_slot_input(self, _now):
        url = slot_url(MONDAY, Meal.DINNER)
        self.assertEqual(self.post(url, {"kind": "recipe"}).status_code, 400)
        self.assertEqual(self.post(url, {"kind": "free", "note": " "}).status_code, 400)
        self.assertEqual(self.get("/menu/2026-02-30/diner/").status_code, 404)
        self.assertEqual(self.get("/menu/2026-09-28/gouter/").status_code, 404)
        self.assertFalse(MealSlot.objects.exists())

    def test_cannot_plan_another_familys_recipe(self, _now):
        foreign = Recipe.objects.create(family=make_family(name="Autre"), name="Intrus")
        response = self.post(
            slot_url(MONDAY, Meal.DINNER), {"kind": "recipe", "recipe": foreign.pk}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MealSlot.objects.exists())

    def test_home_shows_tonights_dinner_with_recipe_link(self, _now):
        self.assertContains(self.get(reverse("tasks:home")), "Choisir le dîner")
        MealSlot.objects.create(
            family=self.family,
            date=MONDAY,
            meal=Meal.DINNER,
            kind=MealKind.RECIPE,
            recipe=self.recipe,
        )
        response = self.get(reverse("tasks:home"))
        self.assertContains(response, "Ce soir au menu")
        self.assertContains(response, reverse("meals:recipe_detail", args=[self.recipe.pk]))
        self.assertContains(response, "45 min")

    def test_home_shows_free_dinner(self, _now):
        MealSlot.objects.create(
            family=self.family,
            date=MONDAY,
            meal=Meal.DINNER,
            kind=MealKind.OUTSIDE,
            note="chez mamie",
        )
        self.assertContains(self.get(reverse("tasks:home")), "Extérieur · chez mamie")


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class MealsPermissionTests(SecureClientMixin, TestCase):
    """Parents seuls gèrent ; enfants en lecture seule sur l'écran partagé ; isolation."""

    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.child = join(self.family, "Lina")  # compte enfant
        self.recipe = Recipe.objects.create(family=self.family, name="Couscous")
        self.ingredient = RecipeIngredient.objects.create(recipe=self.recipe, name="Semoule")
        MealSlot.objects.create(
            family=self.family,
            date=MONDAY,
            meal=Meal.DINNER,
            kind=MealKind.RECIPE,
            recipe=self.recipe,
        )
        other = make_family(name="Autre")
        self.other_parent = join(other, "Max")
        self.foreign = Recipe.objects.create(family=other, name="Intrus")
        self.foreign_ingredient = RecipeIngredient.objects.create(recipe=self.foreign, name="X")

    def parent_urls(self, recipe, ingredient):
        return [
            ("get", reverse("meals:menu")),
            ("get", reverse("meals:recipes")),
            ("get", slot_url(MONDAY, Meal.DINNER)),
            ("post", slot_url(MONDAY, Meal.DINNER)),
            ("get", reverse("meals:recipe_detail", args=[recipe.pk])),
            ("post", reverse("meals:recipe_edit", args=[recipe.pk])),
            ("post", reverse("meals:recipe_favorite", args=[recipe.pk])),
            ("get", reverse("meals:recipe_delete", args=[recipe.pk])),
            ("post", reverse("meals:recipe_delete", args=[recipe.pk])),
            ("post", reverse("meals:ingredient_add", args=[recipe.pk])),
            ("post", reverse("meals:ingredient_delete", args=[ingredient.pk])),
        ]

    def test_anonymous_is_redirected_to_login(self, _now):
        for method, url in self.parent_urls(self.recipe, self.ingredient):
            with self.subTest(url=url):
                response = getattr(self, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response["Location"])

    def test_child_account_cannot_manage(self, _now):
        self.client.force_login(self.child)
        for method, url in self.parent_urls(self.recipe, self.ingredient):
            with self.subTest(url=url):
                self.assertEqual(getattr(self, method)(url, {"kind": "none"}).status_code, 403)
        self.assertTrue(MealSlot.objects.exists())
        self.assertTrue(Recipe.objects.filter(pk=self.recipe.pk).exists())

    def test_other_family_objects_are_404(self, _now):
        self.client.force_login(self.parent)
        urls = self.parent_urls(self.foreign, self.foreign_ingredient)[4:]
        for method, url in urls:
            with self.subTest(url=url):
                self.assertEqual(getattr(self, method)(url, {"name": "Piraté"}).status_code, 404)
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.name, "Intrus")
        self.assertTrue(RecipeIngredient.objects.filter(pk=self.foreign_ingredient.pk).exists())

    def test_other_family_menu_is_not_visible(self, _now):
        self.client.force_login(self.other_parent)
        response = self.get(reverse("meals:menu"))
        self.assertNotContains(response, "Couscous")

    def test_child_account_reads_menu_on_shared_display(self, _now):
        self.client.force_login(self.child)
        response = self.get(reverse("display:menu"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Couscous")
        self.assertNotContains(response, reverse("meals:slot_edit", args=["2026-09-28", "dinner"]))
        self.assertNotContains(response, reverse("shopping:index"))

    def test_shared_device_reads_menu_but_cannot_write(self, _now):
        self.client.force_login(self.parent)
        self.post(reverse("display:activate"), {"name": "Tablette"})  # ferme la session parent
        self.assertContains(self.get(reverse("display:menu")), "Couscous")
        self.assertContains(self.get(reverse("display:board")), reverse("display:menu"))
        for method, url in self.parent_urls(self.recipe, self.ingredient):
            with self.subTest(url=url):
                self.assertEqual(getattr(self, method)(url).status_code, 302)  # vers la connexion
        self.assertTrue(MealSlot.objects.exists())

    def test_shared_menu_requires_device_or_login(self, _now):
        self.assertEqual(self.get(reverse("display:menu")).status_code, 302)
