"""Périodes de la journée (matin / midi / soir), calculées sur l'heure serveur.

Bornes (heure de Paris, TIME_ZONE) :
- matin : 04:00 → 11:00
- midi  : 11:00 → 17:00
- soir  : 17:00 → 04:00 le lendemain (la routine du coucher reste « soir »)

Entre minuit et 04:00, on est encore le soir… mais du jour civil courant :
la date des validations reste `timezone.localdate()`. Cas marginal assumé.
"""

import datetime

from django.db import models
from django.utils import timezone


class Period(models.TextChoices):
    MORNING = "morning", "Matin"
    NOON = "noon", "Midi"
    EVENING = "evening", "Soir"


# Heure de début de chaque période, dans l'ordre de la journée.
PERIOD_STARTS = (
    (datetime.time(4, 0), Period.MORNING),
    (datetime.time(11, 0), Period.NOON),
    (datetime.time(17, 0), Period.EVENING),
)


def period_at(moment: datetime.time) -> Period:
    """Période correspondant à une heure locale."""
    current = Period.EVENING  # avant 04:00 : la soirée de la veille continue
    for start, period in PERIOD_STARTS:
        if moment >= start:
            current = period
    return current


def current_period(now: datetime.datetime | None = None) -> Period:
    now = timezone.localtime(now)
    return period_at(now.time())


def seconds_until_next_period(now: datetime.datetime | None = None) -> int:
    """Secondes avant le prochain changement de période (rechargement de l'écran partagé)."""
    now = timezone.localtime(now)
    for start, _ in PERIOD_STARTS:
        candidate = now.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
        if candidate > now:
            return int((candidate - now).total_seconds())
    first = PERIOD_STARTS[0][0]
    tomorrow = now + datetime.timedelta(days=1)
    candidate = tomorrow.replace(hour=first.hour, minute=first.minute, second=0, microsecond=0)
    return int((candidate - now).total_seconds())
