"""Cochages faits en magasin, même sans réseau, puis envoyés d'un bloc.

Chaque changement porte l'heure où il a été fait sur le téléphone. Pour un article,
le changement le plus récent gagne : si l'autre parent a coché ou décoché après,
le changement plus ancien est ignoré (et l'écran reprend l'état du serveur). Une
heure dans le futur (horloge du téléphone en avance) est ramenée à maintenant.
Articles d'une autre famille, supprimés ou « à la maison » : ignorés.
"""

import datetime

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import ShoppingItem, Status

MAX_CHANGES = 500


def _when(raw, now):
    try:
        moment = parse_datetime(str(raw))
    except ValueError:
        moment = None
    if moment is None:
        return None
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment, datetime.UTC)
    return min(moment, now)


@transaction.atomic
def apply_changes(family, changes: list) -> dict:
    now = timezone.now()
    latest = {}  # id → (heure, coché) : le plus récent de ce lot par article
    for change in changes:
        if not isinstance(change, dict):
            continue
        try:
            pk = int(change.get("id"))
        except (TypeError, ValueError):
            continue
        moment = _when(change.get("at"), now)
        if moment is None or not isinstance(change.get("done"), bool):
            continue
        if pk not in latest or moment >= latest[pk][0]:
            latest[pk] = (moment, change["done"])
    applied = ignored = 0
    items = ShoppingItem.objects.for_family(family).select_for_update().filter(pk__in=latest)
    found = {item.pk: item for item in items}
    for pk, (moment, done) in latest.items():
        item = found.get(pk)
        if item is None or item.status == Status.AT_HOME:
            ignored += 1
            continue
        if item.status_changed_at and item.status_changed_at > moment:
            ignored += 1  # quelqu'un a changé l'article après
            continue
        item.set_status(Status.BOUGHT if done else Status.TO_BUY, at=moment)
        applied += 1
    return {"applied": applied, "ignored": ignored}


def store_states(family) -> dict:
    """{id: coché} des articles de la page magasin (hors « à la maison »)."""
    return {
        str(pk): status == Status.BOUGHT
        for pk, status in ShoppingItem.objects.for_family(family)
        .exclude(status=Status.AT_HOME)
        .values_list("pk", "status")
    }
