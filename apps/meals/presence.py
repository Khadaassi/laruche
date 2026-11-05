"""Combien serons-nous à table ? Calculé depuis le planning, modifiable repas par repas.

Règles (simples et visibles dans le menu) :
- toutes les personnes de la famille, sauf les absents (vacances, malade…) ;
- le **midi**, un enfant qui a école ce jour-là et mange à la cantine, au sandwich
  (APC) ou « ailleurs » n'est pas à la maison ;
- un nombre saisi sur le repas (`MealSlot.guests`) remplace le calcul.
"""

import datetime
from dataclasses import dataclass

from apps.absences.selectors import absences_range
from apps.families.models import Person
from apps.school.models import Lunch
from apps.school.selectors import school_days_range

from .models import Meal

AWAY_AT_LUNCH = {Lunch.CANTEEN, Lunch.PACKED, Lunch.OTHER}


@dataclass(frozen=True)
class Presence:
    count: int
    away: tuple[str, ...] = ()  # prénoms absents de ce repas (pour l'expliquer)

    @property
    def explanation(self) -> str:
        return f"sans {', '.join(self.away)}" if self.away else "toute la famille"


def presence_range(family, start: datetime.date, days: int) -> dict:
    """{(date, repas): Presence} pour chaque jour de [start, start + days[, sans écrire."""
    people = list(Person.objects.for_family(family))
    absences = absences_range(family, start, days)
    school = school_days_range(family, start, days)
    result = {}
    for offset in range(days):
        day = start + datetime.timedelta(days=offset)
        for meal in (Meal.LUNCH, Meal.DINNER):
            away = []
            for person in people:
                if absences[day].is_absent(person.pk):
                    away.append(person.name)
                    continue
                school_day = school[day].get(person.pk)
                if (
                    meal == Meal.LUNCH
                    and school_day
                    and school_day.has_school
                    and school_day.lunch in AWAY_AT_LUNCH
                ):
                    away.append(person.name)
            result[(day, meal)] = Presence(len(people) - len(away), tuple(away))
    return result


def eaters(slot, presence: dict) -> int:
    """Convives d'un repas : le nombre saisi, sinon le calcul (au moins 1 si quelqu'un mange)."""
    if slot.guests:
        return slot.guests
    found = presence.get((slot.date, slot.meal))
    return found.count if found else 0
