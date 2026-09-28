"""Soldes d'étoiles : gagnées (une par journée complète + solde de départ) − dépensées.

Voir domain-model/SKILL.md, section « Étoiles ».
"""

import datetime
from dataclasses import dataclass

from django.db.models import Count, Sum

from apps.families.models import Person
from apps.household.selectors import chores_by_day
from apps.tasks.selectors import tasks_for_day

from .models import DayStar, StarDebit, StarOpeningBalance

STAR_TIER = 10  # un palier tous les 10 étoiles gagnées


@dataclass(frozen=True)
class StarBalance:
    person: Person
    earned: int
    spent: int

    @property
    def balance(self) -> int:
        return self.earned - self.spent

    @property
    def tier(self) -> int:
        """Paliers atteints (sur les étoiles gagnées : la dépense ne fait rien perdre)."""
        return self.earned // STAR_TIER

    @property
    def to_next_tier(self) -> int:
        return STAR_TIER - self.earned % STAR_TIER


def balances(family, people=None) -> dict[int, StarBalance]:
    """{person_id: StarBalance} pour les enfants de la famille, en trois requêtes."""
    children = list(Person.objects.for_family(family).children())
    if people is not None:
        wanted = {p.pk for p in people}
        children = [c for c in children if c.pk in wanted]
    ids = [c.pk for c in children]
    earned = dict.fromkeys(ids, 0)
    stars = DayStar.objects.filter(person_id__in=ids).values("person_id").annotate(n=Count("pk"))
    for row in stars:
        earned[row["person_id"]] = row["n"]
    # Solde de départ (reprise d'une autre application) : des étoiles déjà gagnées.
    opening = StarOpeningBalance.objects.filter(person_id__in=ids)
    for person_id, amount in opening.values_list("person_id", "amount"):
        earned[person_id] += amount
    spent = dict.fromkeys(ids, 0)
    for row in (
        StarDebit.objects.filter(person_id__in=ids).values("person_id").annotate(n=Sum("amount"))
    ):
        spent[row["person_id"]] = row["n"]
    return {c.pk: StarBalance(c, earned[c.pk], spent[c.pk]) for c in children}


def day_progress(person, day: datetime.date) -> tuple[int, int]:
    """(cochées, prévues) pour la journée entière d'une personne.

    Compte ses tâches du jour, **toutes périodes** (matin, midi, soir), et le
    ménage qui lui est assigné ce jour-là. Mêmes règles que l'affichage : une
    tâche hors de sa période de dates ou d'une personne absente (vacances,
    malade) n'est pas prévue. Absente ou sans rien de prévu : (0, 0).
    """
    tasks = tasks_for_day(person.family, day, people=[person])
    chores = [o for o in chores_by_day(person.family, day, 1)[day] if o.person.pk == person.pk]
    states = [t.is_done for t in tasks] + [o.is_done for o in chores]
    return sum(states), len(states)


def pot(family) -> int:
    """Pot commun : somme des soldes positifs des enfants."""
    return sum(max(b.balance, 0) for b in balances(family).values())
