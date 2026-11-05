"""Transfert menu → courses.

1. `week_needs` additionne les ingrédients des recettes au menu d'une semaine,
   **adaptés au nombre de convives** (`meals.presence`) : quantité × convives / portions
   de la recette (une recette pour 4 servie à 6 → ×1,5). Pièces, boîtes et paquets
   sont arrondis à l'unité supérieure, cuillères à la demi.
   même ingrédient (nom normalisé) et même grandeur → une seule ligne.
   g/kg et ml/cl/l se convertissent ; unités différentes et non convertibles
   (200 g de farine + 2 c. à soupe de farine) → deux lignes. Une recette
   prévue deux fois compte deux fois.
2. `build_plan` compare ces besoins aux articles « menu » déjà sur la liste.
   Rien n'est écrit : c'est l'aperçu montré avant de confirmer.
3. `apply_transfer` applique le plan. Un article déjà coché (acheté) ou mis
   « à la maison » dont la quantité a changé est un **conflit** : il n'est
   jamais modifié sans une décision explicite (garder / remettre à acheter).

Les produits ajoutés à la main ne sont jamais touchés par le transfert.
"""

import datetime
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal

from django.db import transaction

from apps.families.models import Family
from apps.meals.models import MealKind, MealSlot, RecipeIngredient
from apps.meals.presence import eaters, presence_range
from apps.meals.units import dimension, format_quantity, from_base, normalize_name, to_base

from .models import Origin, ShoppingItem, ShoppingTransfer, Status

KEEP, REBUY = "keep", "rebuy"
DECISIONS = {KEEP, REBUY}
RECIPES_MAX = 200
NO_QUANTITY = "-"


@dataclass
class Need:
    """Une ligne de courses calculée depuis le menu."""

    key: str
    name: str
    quantity: Decimal | None
    unit: str
    recipes: list = field(default_factory=list)

    @property
    def recipes_label(self) -> str:
        return " · ".join(self.recipes)[:RECIPES_MAX]

    @property
    def quantity_display(self) -> str:
        return format_quantity(self.quantity, self.unit)


WHOLE_UNITS = {"piece", "can", "pack"}
HALF_UNITS = {"tbsp", "tsp"}


def scale_factor(slot, presence) -> Decimal:
    """Convives / portions de la recette ; 1 si personne n'est compté (repas prévu quand même)."""
    count = eaters(slot, presence)
    servings = slot.recipe.servings or 0
    if not count or not servings:
        return Decimal(1)
    return Decimal(count) / Decimal(servings)


def round_for_shopping(quantity: Decimal, unit: str) -> Decimal:
    """Pièces, boîtes, paquets : unité supérieure ; cuillères : demi supérieure ; sinon 0,01."""
    if unit in WHOLE_UNITS:
        return quantity.to_integral_value(rounding=ROUND_CEILING)
    if unit in HALF_UNITS:
        return (quantity * 2).to_integral_value(rounding=ROUND_CEILING) / 2
    return quantity.quantize(Decimal("0.01"))


def merge_key(name: str, quantity, unit: str) -> str:
    kind = NO_QUANTITY if quantity is None else dimension(unit)
    return f"{normalize_name(name)}|{kind}"[:120]


def week_needs(family, monday: datetime.date) -> list[Need]:
    """Ingrédients des recettes au menu de la semaine, quantités additionnées."""
    slots = list(
        MealSlot.objects.for_family(family)
        .filter(
            date__gte=monday,
            date__lt=monday + datetime.timedelta(days=7),
            kind=MealKind.RECIPE,
        )
        .select_related("recipe")
        .order_by("date", "-meal")
    )
    by_recipe = {}
    for ingredient in RecipeIngredient.objects.for_family(family).filter(
        recipe_id__in={slot.recipe_id for slot in slots}
    ):
        by_recipe.setdefault(ingredient.recipe_id, []).append(ingredient)

    presence = presence_range(family, monday, 7)
    groups = {}  # clé → [nom affiché, total en unité de base, unités vues, recettes]
    for slot in slots:
        factor = scale_factor(slot, presence)
        for ingredient in by_recipe.get(slot.recipe_id, []):
            key = merge_key(ingredient.name, ingredient.quantity, ingredient.unit)
            group = groups.setdefault(key, [ingredient.name.strip(), Decimal(0), set(), []])
            if ingredient.quantity is not None:
                group[1] += to_base(ingredient.quantity * factor, ingredient.unit)
                group[2].add(ingredient.unit)
            if slot.recipe.name not in group[3]:
                group[3].append(slot.recipe.name)

    needs = []
    for key, (name, total, units, recipes) in groups.items():
        if units:
            quantity, unit = from_base(total, key.rsplit("|", 1)[1], units)
            quantity = round_for_shopping(quantity, unit)
        else:
            quantity, unit = None, "piece"
        needs.append(Need(key=key, name=name, quantity=quantity, unit=unit, recipes=recipes))
    return needs


def same_quantity(item: ShoppingItem, need: Need) -> bool:
    if item.quantity is None or need.quantity is None:
        return item.quantity is None and need.quantity is None
    return dimension(item.unit) == dimension(need.unit) and to_base(
        item.quantity, item.unit
    ) == to_base(need.quantity, need.unit)


@dataclass
class TransferPlan:
    week: datetime.date
    added: list = field(default_factory=list)  # [Need] : nouveaux articles
    updated: list = field(default_factory=list)  # [(article à acheter, Need)] : quantité changée
    unchanged: list = field(default_factory=list)  # [(article à acheter, Need)]
    conflicts: list = field(default_factory=list)  # [(article coché / à la maison, Need)]
    kept: list = field(default_factory=list)  # [(article coché / à la maison, Need)] inchangé
    removed: list = field(default_factory=list)  # [article] plus au menu, retiré
    stale_bought: list = field(default_factory=list)  # [article acheté] plus au menu, gardé

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.updated or self.conflicts or self.removed)

    @property
    def is_empty(self) -> bool:
        return not (self.has_changes or self.unchanged or self.kept)


def build_plan(family, monday: datetime.date) -> TransferPlan:
    """Compare le menu de la semaine à la liste, sans rien écrire (aperçu)."""
    plan = TransferPlan(week=monday)
    items = {
        item.merge_key: item
        for item in ShoppingItem.objects.for_family(family).filter(origin=Origin.MENU)
    }
    for need in week_needs(family, monday):
        item = items.pop(need.key, None)
        if item is None:
            plan.added.append(need)
        elif item.status == Status.TO_BUY:
            (plan.unchanged if same_quantity(item, need) else plan.updated).append((item, need))
        else:
            (plan.kept if same_quantity(item, need) else plan.conflicts).append((item, need))
    for item in items.values():
        (plan.stale_bought if item.status == Status.BOUGHT else plan.removed).append(item)
    return plan


class MissingDecision(Exception):
    """Un conflit n'a pas reçu de décision (la liste ou le menu a changé entre-temps)."""


@transaction.atomic
def apply_transfer(family, monday: datetime.date, decisions: dict) -> TransferPlan:
    """Applique le transfert. `decisions` : {pk d'article en conflit: "keep" | "rebuy"}.

    Le plan est recalculé sous verrou de la famille : si un conflit n'a pas de
    décision valide, rien n'est écrit (MissingDecision).
    """
    Family.objects.select_for_update().filter(pk=family.pk).first()
    plan = build_plan(family, monday)
    if any(decisions.get(item.pk) not in DECISIONS for item, _ in plan.conflicts):
        raise MissingDecision

    ShoppingItem.objects.bulk_create(
        ShoppingItem(
            family=family,
            name=need.name[:80],
            quantity=need.quantity,
            unit=need.unit,
            origin=Origin.MENU,
            merge_key=need.key,
            recipes=need.recipes_label,
        )
        for need in plan.added
    )
    to_update = []
    for item, need in plan.updated + plan.unchanged + plan.kept + plan.conflicts:
        item.quantity, item.unit, item.recipes = need.quantity, need.unit, need.recipes_label
        to_update.append(item)
    for item, _ in plan.conflicts:
        if decisions[item.pk] == REBUY:
            item.status = Status.TO_BUY
    ShoppingItem.objects.bulk_update(to_update, ["quantity", "unit", "recipes", "status"])
    ShoppingItem.objects.filter(pk__in=[item.pk for item in plan.removed]).delete()
    ShoppingTransfer.objects.update_or_create(family=family, defaults={"week": monday})
    return plan


def clear_bought(family) -> int:
    """Retire les articles achetés ; les produits habituels repassent « à acheter »."""
    bought = ShoppingItem.objects.for_family(family).filter(status=Status.BOUGHT)
    bought.filter(recurring=True).update(status=Status.TO_BUY)
    deleted, _ = bought.filter(recurring=False).delete()
    return deleted
