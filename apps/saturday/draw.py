"""Tirage de la roue du samedi et cycle de vie du plan.

Voir domain-model/SKILL.md, section « Roue du samedi ». Le serveur choisit ;
le navigateur ne fait qu'animer la roue vers le résultat déjà enregistré.
"""

import datetime
import secrets

from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.stars.selectors import pot
from apps.stars.services import NotEnoughStars, refund, spend_from_pot

from .models import PlanStatus, SaturdayActivity, SaturdayPlan, season_of

_RNG = secrets.SystemRandom()

MAX_SPINS = 3  # le premier tirage + 2 relances
RECENT_WINDOW_WEEKS = 8
MIN_WEIGHT = 0.1


class CostFilter(models.TextChoices):
    FREE = "free", "Gratuit"
    ANY = "any", "Peu importe"
    STARS = "stars", "J'ai des étoiles à dépenser"


class PlaceFilter(models.TextChoices):
    OUTING = "outing", "Sortie"
    HOME = "home", "Maison"
    ANY = "any", "Peu importe"


class DrawError(Exception):
    """Refus explicite, avec un message à montrer tel quel."""


def target_saturday(today: datetime.date) -> datetime.date:
    """Aujourd'hui si on est samedi, sinon le prochain samedi."""
    return today + datetime.timedelta(days=(5 - today.weekday()) % 7)


def recency_weight(activity: SaturdayActivity, day: datetime.date) -> float:
    """1 si jamais faite ou il y a 8 semaines et plus ; sinon ∝ temps écoulé, plancher 0,1."""
    if activity.last_done_on is None:
        return 1.0
    weeks = (day - activity.last_done_on).days / 7
    if weeks >= RECENT_WINDOW_WEEKS:
        return 1.0
    return max(MIN_WEIGHT, weeks / RECENT_WINDOW_WEEKS)


def eligible_activities(family, day, cost, place, available_stars) -> list[SaturdayActivity]:
    """Activités de la saison du samedi visé, filtrées par lieu et coût.

    Une activité en étoiles n'est éligible que si le pot commun peut la payer.
    """
    activities = SaturdayActivity.objects.for_family(family).in_season(season_of(day))
    if place != PlaceFilter.ANY:
        activities = activities.filter(place=place)
    if cost == CostFilter.FREE:
        activities = activities.filter(is_free=True, star_cost=0)
    elif cost == CostFilter.STARS:
        activities = activities.filter(star_cost__gt=0, star_cost__lte=available_stars)
    else:
        activities = activities.filter(star_cost__lte=available_stars)
    return list(activities)


def pick(activities, day, rng=_RNG) -> SaturdayActivity:
    weights = [recency_weight(a, day) for a in activities]
    return rng.choices(activities, weights=weights, k=1)[0]


def current_plan(family, today) -> SaturdayPlan | None:
    return (
        SaturdayPlan.objects.for_family(family)
        .filter(date=target_saturday(today))
        .select_related("activity", "star_spend")
        .first()
    )


@transaction.atomic
def draw(family, user, today, cost, place, rng=_RNG) -> SaturdayPlan:
    """Un tour de roue pour le samedi visé (premier tirage ou relance).

    Refusé si le samedi est déjà validé, si les 3 tirages sont épuisés, ou si
    aucune activité ne correspond (ce dernier cas ne consomme pas de tirage).
    """
    day = target_saturday(today)
    try:
        with transaction.atomic():
            plan, _ = SaturdayPlan.objects.get_or_create(
                family=family, date=day, defaults={"created_by": user}
            )
    except IntegrityError:
        plan = SaturdayPlan.objects.get(family=family, date=day)
    plan = SaturdayPlan.objects.select_for_update().get(pk=plan.pk)

    if plan.status != PlanStatus.DRAWING:
        raise DrawError("Ce samedi est déjà prévu. Annulez le plan pour retirer au sort.")
    if plan.spins >= MAX_SPINS:
        raise DrawError(
            "Plus de relance : la roue a déjà tourné 3 fois pour ce samedi. "
            "Validez la dernière proposition, c'est ça la surprise !"
        )
    candidates = eligible_activities(family, day, cost, place, pot(family))
    if not candidates:
        raise DrawError("Aucune activité ne correspond à ces choix pour cette saison.")
    choice = pick(candidates, day, rng)
    plan.activity, plan.activity_name = choice, choice.name
    plan.spins += 1
    plan.save(update_fields=["activity", "activity_name", "spins"])
    return plan


@transaction.atomic
def accept(plan: SaturdayPlan) -> SaturdayPlan:
    """« On y va ! » : le plan est validé et les étoiles éventuelles sont payées."""
    # Verrou sur la seule ligne du plan (Postgres refuse FOR UPDATE sur une jointure externe).
    plan = (
        SaturdayPlan.objects.select_for_update(of=("self",))
        .select_related("activity")
        .get(pk=plan.pk)
    )
    if plan.status != PlanStatus.DRAWING or plan.activity is None:
        raise DrawError("Il n'y a pas de proposition à valider.")
    activity = plan.activity
    if activity.needs_stars:
        try:
            plan.star_spend = spend_from_pot(
                plan.family, activity.star_cost, f"Samedi : {activity.name}"
            )
        except NotEnoughStars as error:
            raise DrawError(
                f"Pas assez d'étoiles : il en faut {activity.star_cost} dans le pot commun."
            ) from error
    plan.status = PlanStatus.PLANNED
    plan.save(update_fields=["status", "star_spend"])
    return plan


@transaction.atomic
def mark_done(plan: SaturdayPlan, today: datetime.date) -> None:
    """Le plan passe dans l'historique ; l'activité prend sa date de réalisation."""
    if plan.status != PlanStatus.PLANNED:
        return
    plan.status = PlanStatus.DONE
    plan.done_at = timezone.now()
    plan.save(update_fields=["status", "done_at"])
    if plan.activity_id:
        SaturdayActivity.objects.filter(pk=plan.activity_id).update(
            last_done_on=min(today, plan.date)
        )


@transaction.atomic
def cancel(plan: SaturdayPlan) -> None:
    """Annule un plan validé : étoiles remboursées, tirage rouvert.

    Un tirage en cours ne s'annule pas : ce serait un moyen de remettre le
    compteur de relances à zéro.
    """
    if plan.status != PlanStatus.PLANNED:
        raise DrawError("Seul un plan validé peut être annulé.")
    refund(plan.star_spend)
    plan.delete()


def close_past_plans(family, today: datetime.date) -> None:
    """Samedi passé : plan validé → historique ; tirage non validé → abandonné.

    Appelé paresseusement par les vues (pas de tâche planifiée sur Render gratuit).
    """
    past = SaturdayPlan.objects.for_family(family).filter(date__lt=today)
    for plan in past.filter(status=PlanStatus.PLANNED):
        mark_done(plan, plan.date)
    past.filter(status=PlanStatus.DRAWING).delete()
