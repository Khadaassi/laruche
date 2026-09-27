import datetime
from decimal import Decimal

from django.test import TestCase

from apps.families.tests.factories import make_family
from apps.meals.models import Meal, MealKind, MealSlot, Recipe, RecipeIngredient
from apps.meals.units import format_quantity, normalize_name
from apps.shopping.models import Origin, ShoppingItem, ShoppingTransfer, Status
from apps.shopping.transfer import (
    KEEP,
    REBUY,
    MissingDecision,
    apply_transfer,
    build_plan,
    clear_bought,
    week_needs,
)

MONDAY = datetime.date(2026, 9, 28)


class MenuFixture:
    def setUp(self):
        self.family = make_family()

    def recipe(self, name, *ingredients):
        recipe = Recipe.objects.create(family=self.family, name=name)
        for ing_name, quantity, unit in ingredients:
            RecipeIngredient.objects.create(
                recipe=recipe,
                name=ing_name,
                quantity=None if quantity is None else Decimal(str(quantity)),
                unit=unit,
            )
        return recipe

    def plan_meal(self, recipe, offset=0, meal=Meal.DINNER):
        return MealSlot.objects.update_or_create(
            family=self.family,
            date=MONDAY + datetime.timedelta(days=offset),
            meal=meal,
            defaults={"kind": MealKind.RECIPE, "recipe": recipe},
        )[0]

    def needs(self):
        return {need.name: need for need in week_needs(self.family, MONDAY)}

    def item(self, name):
        return ShoppingItem.objects.get(family=self.family, name=name)


class UnitHelpersTests(TestCase):
    def test_normalize_name_ignores_case_accents_and_spaces(self):
        self.assertEqual(normalize_name("  Crème   FRAÎCHE "), "creme fraiche")
        self.assertEqual(normalize_name("Œufs"), normalize_name("oeufs"))

    def test_format_quantity(self):
        self.assertEqual(format_quantity(Decimal("1.50"), "kg"), "1,5 kg")
        self.assertEqual(format_quantity(Decimal("3"), "piece"), "3")
        self.assertEqual(format_quantity(Decimal("2"), "pack"), "2 paquets")
        self.assertEqual(format_quantity(None, "g"), "")


class QuantityAdditionTests(MenuFixture, TestCase):
    def test_same_ingredient_in_several_recipes_is_summed(self):
        couscous = self.recipe("Couscous", ("Carottes", 4, "piece"), ("Semoule", 500, "g"))
        tajine = self.recipe("Tajine", ("carottes", 3, "piece"), ("Oignon", 1, "piece"))
        self.plan_meal(couscous, 0)
        self.plan_meal(tajine, 2)
        needs = self.needs()
        self.assertEqual(needs["Carottes"].quantity, Decimal("7"))
        self.assertEqual(needs["Carottes"].recipes, ["Couscous", "Tajine"])
        self.assertEqual(needs["Semoule"].quantity, Decimal("500"))
        self.assertEqual(len(needs), 3)

    def test_recipe_planned_twice_counts_twice(self):
        pates = self.recipe("Pâtes", ("Pâtes", 250, "g"))
        self.plan_meal(pates, 0, Meal.LUNCH)
        self.plan_meal(pates, 3)
        self.assertEqual(self.needs()["Pâtes"].quantity, Decimal("500"))

    def test_convertible_units_are_converted(self):
        self.plan_meal(self.recipe("Gâteau", ("Farine", 250, "g"), ("Lait", 25, "cl")), 0)
        self.plan_meal(self.recipe("Crêpes", ("farine", 1, "kg"), ("Lait", Decimal("0.5"), "l")), 1)
        needs = self.needs()
        self.assertEqual((needs["Farine"].quantity, needs["Farine"].unit), (Decimal("1.25"), "kg"))
        self.assertEqual((needs["Lait"].quantity, needs["Lait"].unit), (Decimal("75"), "cl"))

    def test_same_unit_is_kept(self):
        self.plan_meal(self.recipe("A", ("Crème", 20, "cl")), 0)
        self.plan_meal(self.recipe("B", ("Crème", 25, "cl")), 1)
        need = self.needs()["Crème"]
        self.assertEqual(need.quantity_display, "45 cl")

    def test_incompatible_units_stay_on_separate_lines(self):
        self.plan_meal(self.recipe("A", ("Farine", 200, "g")), 0)
        self.plan_meal(self.recipe("B", ("Farine", 2, "tbsp")), 1)
        needs = week_needs(self.family, MONDAY)
        self.assertEqual(sorted((n.quantity_display) for n in needs), ["2 c. à soupe", "200 g"])

    def test_ingredients_without_quantity_are_merged_once(self):
        self.plan_meal(self.recipe("A", ("Sel", None, "piece")), 0)
        self.plan_meal(self.recipe("B", ("sel", None, "piece")), 1)
        needs = week_needs(self.family, MONDAY)
        self.assertEqual(len(needs), 1)
        self.assertIsNone(needs[0].quantity)

    def test_only_the_requested_week_and_recipes_count(self):
        recipe = self.recipe("A", ("Riz", 100, "g"))
        self.plan_meal(recipe, 7)  # semaine suivante
        MealSlot.objects.create(
            family=self.family, date=MONDAY, meal=Meal.LUNCH, kind=MealKind.LEFTOVERS
        )
        other = make_family(name="Autre")
        other_recipe = Recipe.objects.create(family=other, name="X")
        RecipeIngredient.objects.create(recipe=other_recipe, name="Riz", quantity=1, unit="kg")
        MealSlot.objects.create(
            family=other, date=MONDAY, meal=Meal.DINNER, kind=MealKind.RECIPE, recipe=other_recipe
        )
        self.assertEqual(week_needs(self.family, MONDAY), [])

    def test_transfer_creates_menu_items_and_records_the_week(self):
        self.plan_meal(self.recipe("A", ("Riz", 100, "g")), 0)
        self.plan_meal(self.recipe("B", ("Riz", 150, "g")), 1)
        apply_transfer(self.family, MONDAY, {})
        item = self.item("Riz")
        self.assertEqual((item.quantity, item.unit, item.origin), (Decimal("250"), "g", "menu"))
        self.assertEqual(item.status, Status.TO_BUY)
        self.assertEqual(item.recipes, "A · B")
        self.assertEqual(ShoppingTransfer.objects.get(family=self.family).week, MONDAY)


class RetransferTests(MenuFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.couscous = self.recipe(
            "Couscous", ("Carottes", 4, "piece"), ("Pois chiches", 1, "can")
        )
        self.tajine = self.recipe("Tajine", ("Carottes", 3, "piece"))
        self.plan_meal(self.couscous, 0)
        apply_transfer(self.family, MONDAY, {})
        self.carrots = self.item("Carottes")
        self.carrots.status = Status.BOUGHT
        self.carrots.save()

    def test_unchanged_bought_item_stays_checked_without_question(self):
        plan = build_plan(self.family, MONDAY)
        self.assertFalse(plan.has_changes)
        self.assertEqual([item for item, _ in plan.kept], [self.carrots])
        apply_transfer(self.family, MONDAY, {})
        self.assertEqual(self.item("Carottes").status, Status.BOUGHT)

    def test_bought_item_with_new_quantity_is_a_conflict(self):
        self.plan_meal(self.tajine, 2)
        plan = build_plan(self.family, MONDAY)
        self.assertEqual([(i.pk, n.quantity) for i, n in plan.conflicts], [(self.carrots.pk, 7)])
        self.assertTrue(plan.has_changes)

    def test_conflict_without_decision_writes_nothing(self):
        self.plan_meal(self.tajine, 2)
        with self.assertRaises(MissingDecision):
            apply_transfer(self.family, MONDAY, {})
        with self.assertRaises(MissingDecision):
            apply_transfer(self.family, MONDAY, {self.carrots.pk: "écraser"})
        carrots = self.item("Carottes")
        self.assertEqual((carrots.status, carrots.quantity), (Status.BOUGHT, 4))

    def test_keep_checked_decision(self):
        self.plan_meal(self.tajine, 2)
        apply_transfer(self.family, MONDAY, {self.carrots.pk: KEEP})
        carrots = self.item("Carottes")
        self.assertEqual((carrots.status, carrots.quantity), (Status.BOUGHT, 7))
        self.assertEqual(carrots.recipes, "Couscous · Tajine")

    def test_rebuy_decision(self):
        self.plan_meal(self.tajine, 2)
        apply_transfer(self.family, MONDAY, {self.carrots.pk: REBUY})
        carrots = self.item("Carottes")
        self.assertEqual((carrots.status, carrots.quantity), (Status.TO_BUY, 7))

    def test_at_home_item_with_new_quantity_is_also_a_conflict(self):
        chickpeas = self.item("Pois chiches")
        chickpeas.status = Status.AT_HOME
        chickpeas.save()
        self.plan_meal(self.recipe("Houmous", ("Pois chiches", 2, "can")), 3)
        plan = build_plan(self.family, MONDAY)
        self.assertIn(chickpeas.pk, [item.pk for item, _ in plan.conflicts])

    def test_to_buy_item_is_updated_and_removed_items_leave_the_list(self):
        # Pois chiches (à acheter) : le couscous est remplacé par le tajine.
        self.plan_meal(self.tajine, 0)
        plan = build_plan(self.family, MONDAY)
        self.assertEqual([item.name for item in plan.removed], ["Pois chiches"])
        self.assertEqual(plan.conflicts[0][1].quantity, 3)
        apply_transfer(self.family, MONDAY, {self.carrots.pk: KEEP})
        self.assertFalse(ShoppingItem.objects.filter(name="Pois chiches").exists())

    def test_bought_item_no_longer_in_menu_is_kept(self):
        MealSlot.objects.all().delete()
        plan = build_plan(self.family, MONDAY)
        self.assertEqual(plan.stale_bought, [self.carrots])
        apply_transfer(self.family, MONDAY, {})
        self.assertEqual(self.item("Carottes").status, Status.BOUGHT)

    def test_manual_items_are_never_touched(self):
        manual = ShoppingItem.objects.create(family=self.family, name="Carottes", quantity=1)
        self.plan_meal(self.tajine, 2)
        apply_transfer(self.family, MONDAY, {self.carrots.pk: REBUY})
        manual.refresh_from_db()
        self.assertEqual((manual.origin, manual.quantity), (Origin.MANUAL, 1))

    def test_clear_bought_keeps_recurring_items(self):
        ShoppingItem.objects.create(
            family=self.family, name="Lait", recurring=True, status=Status.BOUGHT
        )
        ShoppingItem.objects.create(family=self.family, name="Piles", status=Status.BOUGHT)
        self.assertEqual(clear_bought(self.family), 2)  # carottes + piles
        self.assertEqual(self.item("Lait").status, Status.TO_BUY)
        self.assertFalse(ShoppingItem.objects.filter(name__in=["Piles", "Carottes"]).exists())
