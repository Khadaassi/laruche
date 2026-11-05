"""Envoi des notifications push et règles des rappels programmés."""

import datetime
import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from pywebpush import WebPushException, webpush

from .keys import vapid
from .models import NotificationPrefs, PushSubscription, SentNotification

logger = logging.getLogger(__name__)

DINNER_FROM = datetime.time(15, 0)
DINNER_UNTIL = datetime.time(20, 0)
REVIEW_FROM = datetime.time(17, 0)
SUNDAY = 6


def prefs_for(user) -> NotificationPrefs:
    return NotificationPrefs.objects.filter(user=user).first() or NotificationPrefs(user=user)


def send_to_user(user, title: str, body: str, url: str = "/", tag: str = "") -> int:
    """Envoie à tous les appareils du parent ; renvoie le nombre d'envois réussis."""
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})
    claims = {"sub": getattr(settings, "VAPID_SUBJECT", "https://laruche.onrender.com")}
    delivered = 0
    for sub in PushSubscription.objects.filter(user=user):
        try:
            webpush(
                sub.as_subscription_info(),
                payload,
                vapid_private_key=vapid(),
                vapid_claims=dict(claims),
                timeout=5,
                ttl=6 * 3600,
            )
        except WebPushException as error:
            status = getattr(error.response, "status_code", None)
            if status in (404, 410):
                sub.delete()  # appareil désabonné ou abonnement expiré
            else:
                logger.warning("Push refusé (%s) pour %s", status, user.pk)
            continue
        except Exception:  # réseau : jamais d'erreur visible pour l'utilisateur
            logger.warning("Push impossible pour %s", user.pk, exc_info=True)
            continue
        sub.last_success_at = timezone.now()
        sub.save(update_fields=["last_success_at"])
        delivered += 1
    return delivered


def notify_once(user, kind: str, key: str, **message) -> bool:
    """Envoie au plus une fois par (parent, type, clé) ; True si c'est cet appel qui envoie."""
    try:
        with transaction.atomic():
            SentNotification.objects.create(user=user, kind=kind, key=key)
    except IntegrityError:
        return False
    send_to_user(user, **message)
    return True


def parents_of(family):
    from apps.accounts.models import User
    from apps.families.models import Role

    return User.objects.filter(membership__family=family, membership__role=Role.PARENT)


def notify_day_done(person, day: datetime.date) -> None:
    """Un enfant vient de gagner l'étoile du jour : prévenir les parents (aujourd'hui seulement)."""
    if day != timezone.localdate():
        return
    for parent in parents_of(person.family):
        if prefs_for(parent).day_done:
            notify_once(
                parent,
                "day_done",
                f"{person.pk}-{day.isoformat()}",
                title=f"{person.name} a terminé sa journée",
                body="Toutes ses tâches sont cochées : +1 étoile !",
                url="/",
                tag=f"day-{person.pk}",
            )


def run_scheduled(now: datetime.datetime | None = None) -> dict:
    """Rappels programmés (tâche planifiée) : sans doublon, sans risque à relancer."""
    from apps.families.models import Family
    from apps.meals.models import Meal, MealSlot
    from apps.review.selectors import is_done, review_monday

    now = timezone.localtime(now)
    today, moment = now.date(), now.time()
    sent = {"dinner": 0, "review": 0}
    for family in Family.objects.all():
        parents = list(parents_of(family))
        if not parents or not PushSubscription.objects.filter(user__in=parents).exists():
            continue
        if (
            DINNER_FROM <= moment <= DINNER_UNTIL
            and not MealSlot.objects.filter(family=family, date=today, meal=Meal.DINNER).exists()
        ):
            for parent in parents:
                if prefs_for(parent).dinner and notify_once(
                    parent,
                    "dinner",
                    today.isoformat(),
                    title="Ce soir, on mange quoi ?",
                    body="Le dîner n'est pas encore prévu dans le menu.",
                    url="/menu/",
                    tag="dinner",
                ):
                    sent["dinner"] += 1
        if today.weekday() == SUNDAY and moment >= REVIEW_FROM:
            monday = review_monday(today)
            if not is_done(family, monday):
                for parent in parents:
                    if prefs_for(parent).review and notify_once(
                        parent,
                        "review",
                        monday.isoformat(),
                        title="Revue de la semaine",
                        body="5 minutes pour préparer la semaine qui vient.",
                        url="/revue/",
                        tag="review",
                    ):
                        sent["review"] += 1
    return sent
