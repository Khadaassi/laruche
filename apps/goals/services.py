"""Écritures de « Mon année » (toujours pour l'utilisateur connecté)."""

import datetime

from django.db import transaction

from .defaults import VISION_2027
from .models import Goal, Step, StepLog


def default_year(today: datetime.date) -> int:
    """Année affichée par défaut : la suivante dès novembre (on prépare l'année qui vient)."""
    return today.year + 1 if today.month >= 11 else today.year


@transaction.atomic
def ensure_vision(user, year: int) -> None:
    """Crée le vision board de départ si l'utilisateur n'a aucun objectif cette année-là."""
    if Goal.objects.mine(user, year).exists():
        return
    # `savings` : l'objectif d'épargne reste vide, à fixer par l'utilisatrice.
    for position, (title, icon, journal, _savings, contacts, steps) in enumerate(VISION_2027):
        goal = Goal.objects.create(
            user=user,
            year=year,
            title=title,
            icon=icon,
            position=position,
            journal_label=journal,
            has_contacts=contacts,
        )
        Step.objects.bulk_create(
            Step(goal=goal, title=t, unit=u, daily_target=target, days_per_week=days, position=i)
            for i, (t, u, target, days) in enumerate(steps)
        )


def set_step_value(step: Step, day: datetime.date, value: int) -> None:
    """Valeur du jour (0 = rien) ; idempotent."""
    if value <= 0:
        StepLog.objects.filter(step=step, date=day).delete()
    else:
        StepLog.objects.update_or_create(step=step, date=day, defaults={"value": value})
