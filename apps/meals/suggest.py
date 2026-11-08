"""Menu assisté : propose des recettes pour les repas encore vides d'une semaine.

- Repas visés, d'après les présences (`presence.py`) : chaque dîner où quelqu'un
  mange, et chaque déjeuner où un enfant mange à la maison (mercredi, week-end,
  vacances scolaires, enfant malade…) ; aussi les midis entre adultes si la famille
  l'a choisi (`MealPreferences.adult_lunches`). Sans semaine d'école renseignée, on
  suppose l'école les lundis, mardis, jeudis et vendredis hors vacances. Jamais un
  jour passé, jamais un repas où personne n'est compté.
- Ne remplace **jamais** un repas déjà prévu.
- Favoris d'abord (tirés deux fois plus souvent) ; on évite les recettes servies
  les 14 derniers jours ou déjà au menu de la semaine. Pas assez de recettes : on
  reprend les moins récemment servies.
- **Soirs chargés** (un rendez-vous qui finit après 17 h, ou au moins deux dans la
  journée) : le dîner est pris parmi les recettes **rapides** (≤ 30 min) s'il y en a ;
  les autres repas ne les prennent pas tant qu'il reste un soir chargé à couvrir.
- Tirage reproductible pour une famille et une semaine (même proposition si on
  recommence sur une semaine vide).
"""

import datetime
import random

from django.db import transaction
from django.utils import timezone

from apps.agenda.grid import events_by_day
from apps.holidays.models import SchoolHoliday
from apps.school.models import SchoolDaySchedule

from .models import Meal, MealKind, MealPreferences, MealSlot, Recipe
from .presence import presence_range

# Sans semaine d'école renseignée : midis à la maison supposés (mercredi, week-end).
LUNCH_WEEKDAYS = (2, 5, 6)
RECENT_DAYS = 14
QUICK_MINUTES = 30
EVENING = datetime.time(17, 0)


def busy_evenings(family, monday: datetime.date) -> set[datetime.date]:
    """Jours de la semaine où le soir est chargé (agenda de la famille)."""
    busy = set()
    for day, events in events_by_day(family, monday, 7).items():
        if len(events) >= 2 or any(e.end_time > EVENING for e in events):
            busy.add(day)
    return busy


def is_quick(recipe) -> bool:
    return recipe.prep_minutes is not None and recipe.prep_minutes <= QUICK_MINUTES


def target_slots(family, monday: datetime.date, today: datetime.date) -> list:
    """Repas à prévoir de la semaine [(date, repas)], d'après les présences."""
    presence = presence_range(family, monday, 7)
    adult_lunches = MealPreferences.for_family(family).adult_lunches
    school_known = SchoolDaySchedule.objects.for_family(family).exists()
    sunday = monday + datetime.timedelta(days=6)
    holidays = list(
        SchoolHoliday.objects.for_family(family)
        .filter(start_date__lte=sunday, end_date__gte=monday)
        .values_list("start_date", "end_date")
    )
    slots = []
    for offset in range(7):
        day = monday + datetime.timedelta(days=offset)
        if day < today:
            continue
        lunch = presence.get((day, Meal.LUNCH))
        at_home_guess = (
            school_known
            or day.weekday() in LUNCH_WEEKDAYS
            or any(first <= day <= last for first, last in holidays)
        )
        if lunch and lunch.count and (adult_lunches or (lunch.children and at_home_guess)):
            slots.append((day, Meal.LUNCH))
        dinner = presence.get((day, Meal.DINNER))
        if dinner and dinner.count:
            slots.append((day, Meal.DINNER))
    return slots


def empty_slots(family, monday: datetime.date, today: datetime.date | None = None):
    today = today or timezone.localdate()
    taken = set(
        MealSlot.objects.for_family(family)
        .filter(date__range=(monday, monday + datetime.timedelta(days=6)))
        .values_list("date", "meal")
    )
    return [slot for slot in target_slots(family, monday, today) if slot not in taken]


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
    busy = busy_evenings(family, monday)
    busy_left = sum(1 for day, meal in slots if meal == Meal.DINNER and day in busy)
    created = []
    for day, meal in slots:
        pool = fresh
        if meal == Meal.DINNER and day in busy:
            busy_left -= 1
            pool = [r for r in fresh if is_quick(r)] or fresh
        elif busy_left:
            # Les recettes rapides sont gardées pour les soirs chargés encore à venir.
            pool = [r for r in fresh if not is_quick(r)] or fresh
        if pool:
            weights = [2 if r.is_favorite else 1 for r in pool]
            recipe = rng.choices(pool, weights=weights)[0]
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
