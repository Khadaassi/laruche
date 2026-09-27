"""Dépense d'étoiles depuis le pot commun, au prorata des soldes."""

from django.db import transaction

from apps.families.models import Family

from .models import StarDebit, StarSpend
from .selectors import balances


class NotEnoughStars(Exception):
    """Le pot commun ne suffit pas pour cette dépense."""


def split_cost(available: dict[int, int], cost: int) -> dict[int, int]:
    """Répartit `cost` au prorata de `available` (méthode du plus fort reste).

    Garanties : la somme vaut exactement `cost`, aucune part ne dépasse le solde,
    un solde nul ne contribue pas. Départage des restes égaux : plus gros solde,
    puis identifiant (résultat déterministe).
    """
    available = {pid: amount for pid, amount in available.items() if amount > 0}
    total = sum(available.values())
    if cost > total:
        raise NotEnoughStars
    if cost <= 0:
        return {}
    shares = {pid: cost * amount // total for pid, amount in available.items()}
    remainders = sorted(
        available,
        key=lambda pid: (-(cost * available[pid] % total), -available[pid], pid),
    )
    for pid in remainders[: cost - sum(shares.values())]:
        shares[pid] += 1
    return {pid: share for pid, share in shares.items() if share > 0}


@transaction.atomic
def spend_from_pot(family, cost: int, reason: str) -> StarSpend | None:
    """Débite `cost` étoiles du pot commun ; None si rien à payer.

    La ligne de la famille est verrouillée : deux dépenses simultanées ne
    peuvent pas dépenser deux fois les mêmes étoiles.
    """
    if cost <= 0:
        return None
    Family.objects.select_for_update().get(pk=family.pk)
    available = {pid: b.balance for pid, b in balances(family).items()}
    shares = split_cost(available, cost)
    spend = StarSpend.objects.create(family=family, total=cost, reason=reason)
    StarDebit.objects.bulk_create(
        StarDebit(spend=spend, person_id=pid, amount=amount) for pid, amount in shares.items()
    )
    return spend


def refund(spend: StarSpend | None) -> None:
    """Annule une dépense : chaque enfant récupère exactement sa part."""
    if spend is not None:
        spend.delete()
