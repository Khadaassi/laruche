"""Occurrences des tâches de ménage sur une période (semainier)."""

import datetime
from dataclasses import dataclass

from .models import ChoreCompletion, HouseholdChore


@dataclass
class ChoreOccurrence:
    chore: HouseholdChore
    date: datetime.date
    is_done: bool


def chores_by_day(family, start: datetime.date, days: int = 7) -> dict:
    """{date: [ChoreOccurrence]} pour chaque jour de [start, start + days[.

    Deux requêtes, quel que soit le nombre de jours.
    """
    end = start + datetime.timedelta(days=days)
    chores = list(
        HouseholdChore.objects.for_family(family)
        .filter(start_date__lt=end)
        .select_related("assignee")
    )
    done = set(
        ChoreCompletion.objects.filter(
            chore__family=family, date__gte=start, date__lt=end
        ).values_list("chore_id", "date")
    )
    result = {}
    for offset in range(days):
        day = start + datetime.timedelta(days=offset)
        result[day] = [
            ChoreOccurrence(chore, day, (chore.pk, day) in done)
            for chore in chores
            if chore.occurs_on(day)
        ]
    return result


def set_chore_done(chore: HouseholdChore, day: datetime.date, done: bool) -> None:
    """Fixe l'état (idempotent), comme pour les tâches enfants."""
    if done:
        ChoreCompletion.objects.get_or_create(chore=chore, date=day)
    else:
        ChoreCompletion.objects.filter(chore=chore, date=day).delete()
