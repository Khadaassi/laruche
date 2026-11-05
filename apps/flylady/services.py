"""Écritures FlyLady : contenu de départ et coches."""

import datetime

from django.db import IntegrityError, transaction

from . import defaults
from .models import FlyCheck, FlyMission, FlyRoutineItem, FlyZone, RoutineKind


@transaction.atomic
def ensure_defaults(family) -> None:
    """Crée le contenu de départ à la première visite (rien si déjà fait)."""
    if FlyZone.objects.for_family(family).exists():
        return
    items = []
    for kind, titles in (
        (RoutineKind.MORNING, defaults.MORNING),
        (RoutineKind.EVENING, defaults.EVENING),
        (RoutineKind.BLESSING, defaults.BLESSING),
    ):
        items += [
            FlyRoutineItem(family=family, kind=kind, title=t, position=i)
            for i, t in enumerate(titles)
        ]
    FlyRoutineItem.objects.bulk_create(items)
    for number, name, missions in defaults.ZONES:
        try:
            with transaction.atomic():
                zone = FlyZone.objects.create(family=family, number=number, name=name)
        except IntegrityError:  # deux premières visites simultanées
            return
        FlyMission.objects.bulk_create(
            FlyMission(zone=zone, title=t, position=i) for i, t in enumerate(missions)
        )


def set_checked(family, day: datetime.date, key: str, checked: bool) -> None:
    """Fixe l'état (idempotent)."""
    if checked:
        FlyCheck.objects.get_or_create(family=family, date=day, key=key)
    else:
        FlyCheck.objects.filter(family=family, date=day, key=key).delete()
