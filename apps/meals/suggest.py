"""Menu assisté : propose des recettes pour les repas encore vides d'une semaine.

- Repas visés : tous les dîners, et le déjeuner du mercredi, samedi et dimanche
  (les autres midis, les enfants mangent à l'école). Jamais un jour passé.
- Ne remplace **jamais** un repas déjà prévu.
- Favoris d'abord (tirés deux fois plus souvent) ; on évite les recettes servies
  les 14 derniers jours ou déjà au menu de la semaine. Pas assez de recettes : on
  reprend les moins récemment servies.
- Tirage reproductible pour une famille et une semaine (même proposition si on
  recommence sur une semaine vide).
"""

import datetime
import random

from django.db import transaction
from django.utils import timezone

from .models import Meal, MealKind, MealSlot, Recipe

LUNCH_WEEKDAYS = (2, 5, 6)  # mercredi, samedi, dimanche
RECENT_DAYS = 14


def target_slots(monday: datetime.date, today: datetime.date) -> list[tuple[datetime.date, str]]:
    slots = []
    for offset in range(7):
        day = monday + datetime.timedelta(days=offset)
        if day < today:
            continue
        if day.weekday() in LUNCH_WEEKDAYS:
            slots.append((day, Meal.LUNCH))
        slots.append((day, Meal.DINNER))
    return slots


def empty_slots(family, monday: datetime.date, today: datetime.date | None = None):
    today = today or timezone.localdate()
    taken = set(
        MealSlot.objects.for_family(family)
        .filter(date__range=(monday, monday + datetime.timedelta(days=6)))
        .values_list("date", "meal")
    )
    return [slot for slot in target_slots(monday, today) if slot not in taken]


@transaction.atomic
def suggest_week(family, monday: datetime.date) -> list[MealSlot]:
    """Remplit les repas vides de la semaine ; renvoie les repas créés."""
    slots = empty_slots(family, monday)
    recipes = list(Recipe.objects.for_family(family))
    if not slots or not recipes:
        return []
    sunday = monday + datetime.timedelta(days=6)
    last_served = {}
    for recipe_id, day in (
        MealSlot.objects.for_family(family)
        .filter(recipe__isnull=False, date__gte=monday - datetime.timedelta(days=RECENT_DAYS))
        .filter(date__lte=sunday)
        .values_list("recipe_id", "date")
    ):
        last_served[recipe_id] = max(day, last_served.get(recipe_id, day))
    rng = random.Random(f"{family.pk}-{monday.isoformat()}")  # noqa: S311 (pas de sécurité ici)
    fresh = [r for r in recipes if r.pk not in last_served]
    # Ordre de repli : jamais servies d'abord, puis les moins récentes.
    stale = sorted(
        (r for r in recipes if r.pk in last_served), key=lambda r: (last_served[r.pk], r.pk)
    )
    created = []
    for day, meal in slots:
        if fresh:
            weights = [2 if r.is_favorite else 1 for r in fresh]
            recipe = rng.choices(fresh, weights=weights)[0]
            fresh.remove(recipe)
        else:
            recipe = stale.pop(0)
        stale.append(recipe)  # pourra revenir en tout dernier recours
        created.append(
            MealSlot.objects.create(
                family=family, date=day, meal=meal, kind=MealKind.RECIPE, recipe=recipe
            )
        )
    return created
