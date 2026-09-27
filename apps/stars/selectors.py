"""Soldes d'étoiles : gagnées (déduites des validations) − dépensées.

Voir domain-model/SKILL.md, section « Étoiles ».
"""

from dataclasses import dataclass

from django.db.models import Count, Sum

from apps.families.models import Person
from apps.household.models import ChoreCompletion
from apps.tasks.models import TaskCompletion

from .models import StarDebit

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
    for row in (
        TaskCompletion.objects.filter(task__person_id__in=ids)
        .values("task__person_id")
        .annotate(n=Count("pk"))
    ):
        earned[row["task__person_id"]] += row["n"]
    for row in (
        ChoreCompletion.objects.filter(chore__assignee_id__in=ids)
        .values("chore__assignee_id")
        .annotate(n=Count("pk"))
    ):
        earned[row["chore__assignee_id"]] += row["n"]
    spent = dict.fromkeys(ids, 0)
    for row in (
        StarDebit.objects.filter(person_id__in=ids).values("person_id").annotate(n=Sum("amount"))
    ):
        spent[row["person_id"]] = row["n"]
    return {c.pk: StarBalance(c, earned[c.pk], spent[c.pk]) for c in children}


def pot(family) -> int:
    """Pot commun : somme des soldes positifs des enfants."""
    return sum(max(b.balance, 0) for b in balances(family).values())
