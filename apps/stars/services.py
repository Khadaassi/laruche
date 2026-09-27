"""Étoiles : gain d'une journée complète, dépense depuis le pot commun."""

import datetime

from django.db import transaction
from django.utils import timezone

from apps.families.models import Family

from .models import DayStar, StarDebit, StarOpeningBalance, StarSpend, TierCelebration
from .selectors import balances, day_progress


def award_day_star(person, day: datetime.date) -> bool:
    """Donne l'étoile du jour si toute la journée de l'enfant est cochée.

    À appeler après chaque cochage d'une tâche ou d'un ménage. Renvoie True
    seulement pour l'appel qui crée l'étoile. Idempotent : une journée déjà
    récompensée ne donne jamais une deuxième étoile (contrainte unique en
    base, y compris entre deux requêtes simultanées), même après un
    décochage puis un recochage. Rien pour un parent, une journée future ou
    une journée sans rien de prévu (absence).
    """
    if not person.is_child or day > timezone.localdate():
        return False
    done, due = day_progress(person, day)
    if due == 0 or done < due:
        return False
    _, created = DayStar.objects.get_or_create(person=person, date=day)
    return created


class OpeningBalanceError(Exception):
    """Solde de départ refusé (pas un enfant, montant nul, déjà enregistré)."""


@transaction.atomic
def grant_opening_balance(person, amount: int, reason: str) -> StarOpeningBalance:
    """Enregistre le solde de départ d'un enfant, une seule fois.

    Le palier atteint par ce seul solde est marqué comme déjà fêté : ces étoiles
    ont été gagnées ailleurs, l'écran partagé ne fête que les paliers franchis
    ensuite dans La Ruche. Refus (rien n'est écrit) si ce n'est pas un enfant, si
    le montant n'est pas positif ou si l'enfant a déjà un solde de départ (la
    contrainte OneToOne le garantit aussi en base).
    """
    if not person.is_child:
        raise OpeningBalanceError(f"{person} n'est pas un enfant.")
    if amount <= 0:
        raise OpeningBalanceError("Le solde de départ doit être positif.")
    if StarOpeningBalance.objects.filter(person=person).exists():
        raise OpeningBalanceError(f"{person} a déjà un solde de départ.")
    opening = StarOpeningBalance.objects.create(person=person, amount=amount, reason=reason)
    tier = balances(person.family, people=[person])[person.pk].tier
    if tier:
        celebration, _ = TierCelebration.objects.get_or_create(person=person)
        if celebration.tier < tier:
            celebration.tier = tier
            celebration.save(update_fields=["tier", "updated_at"])
    return opening


def claim_day_celebration(person, day: datetime.date) -> bool:
    """« Journée terminée ! » à montrer maintenant pour cet enfant ?

    Vrai une seule fois par étoile du jour : `celebrated` n'avance que par un
    UPDATE conditionnel atomique, comme pour les paliers.
    """
    pending = DayStar.objects.filter(person=person, date=day, celebrated=False)
    return bool(pending.update(celebrated=True))


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


def claim_tier_celebration(balance) -> int | None:
    """Palier à fêter maintenant pour cet enfant, ou None.

    Renvoie le nouveau palier une seule fois : la ligne n'avance que si le
    palier atteint dépasse le dernier fêté (UPDATE conditionnel atomique, donc
    pas de doublon même si deux écrans affichent la page en même temps). Un
    décochage puis recochage ne refête pas un palier déjà fêté ; plusieurs
    paliers franchis d'un coup donnent une seule célébration (le plus haut).
    """
    tier = balance.tier
    if tier < 1:
        return None
    TierCelebration.objects.get_or_create(person=balance.person)
    advanced = TierCelebration.objects.filter(person=balance.person, tier__lt=tier).update(
        tier=tier
    )
    return tier if advanced else None
