"""Occurrences des tâches de ménage sur une période (semainier)."""

import datetime
from dataclasses import dataclass

from django.db import transaction

from apps.absences.selectors import absences_range

from .models import ChoreCompletion, ChoreSwap, HouseholdChore, monday_of


@dataclass
class ChoreOccurrence:
    chore: HouseholdChore
    date: datetime.date
    is_done: bool
    person: object  # families.Person chargée ce jour-là (alternance comprise)


def chores_by_day(family, start: datetime.date, days: int = 7) -> dict:
    """{date: [ChoreOccurrence]} pour chaque jour de [start, start + days[.

    Quatre requêtes, quel que soit le nombre de jours. Sans les jours où la
    personne chargée de la tâche (alternance comprise) est absente.
    """
    end = start + datetime.timedelta(days=days)
    chores = list(
        HouseholdChore.objects.for_family(family)
        .filter(start_date__lt=end)
        .select_related("assignee", "alternate")
        .prefetch_related("swaps")
    )
    done = set(
        ChoreCompletion.objects.filter(
            chore__family=family, date__gte=start, date__lt=end
        ).values_list("chore_id", "date")
    )
    absences = absences_range(family, start, days)
    result = {}
    for offset in range(days):
        day = start + datetime.timedelta(days=offset)
        occurrences = []
        for chore in chores:
            if not chore.occurs_on(day):
                continue
            person = chore.person_on(day)
            # Ménage d'une personne absente (vacances, malade) : suspendu ce jour-là.
            if not absences[day].is_absent(person.pk):
                occurrences.append(ChoreOccurrence(chore, day, (chore.pk, day) in done, person))
        result[day] = occurrences
    return result


@dataclass
class Rotation:
    """Tâches en alternance entre les deux mêmes personnes, pour une semaine."""

    people: tuple  # (Person, Person), ordre stable
    chores: list  # [(HouseholdChore, Person chargée cette semaine)]

    @property
    def chore_ids(self) -> list[int]:
        return [chore.pk for chore, _ in self.chores]


def rotations(family, day: datetime.date) -> list[Rotation]:
    """Alternances de la famille regroupées par paire de personnes, avec qui
    fait quoi la semaine de `day`. Un échange s'applique à toute la paire."""
    chores = (
        HouseholdChore.objects.for_family(family)
        .filter(alternate__isnull=False)
        .select_related("assignee", "alternate")
        .prefetch_related("swaps")
    )
    groups: dict[tuple, Rotation] = {}
    for chore in chores:
        people = tuple(sorted((chore.assignee, chore.alternate), key=lambda p: p.pk))
        key = tuple(p.pk for p in people)
        groups.setdefault(key, Rotation(people, [])).chores.append((chore, chore.person_on(day)))
    return list(groups.values())


@transaction.atomic
def swap_rotation(chores, day: datetime.date) -> None:
    """Inverse l'alternance de ces tâches à partir de la semaine de `day`.

    Refaire l'échange la même semaine l'annule (retour à l'ordre d'avant).
    Les semaines passées ne changent pas.
    """
    week = monday_of(day)
    for chore in chores:
        deleted, _ = ChoreSwap.objects.filter(chore=chore, week=week).delete()
        if not deleted:
            ChoreSwap.objects.create(chore=chore, week=week)


def set_chore_done(chore: HouseholdChore, day: datetime.date, done: bool) -> None:
    """Fixe l'état (idempotent), comme pour les tâches enfants."""
    if done:
        ChoreCompletion.objects.get_or_create(chore=chore, date=day)
    else:
        ChoreCompletion.objects.filter(chore=chore, date=day).delete()
