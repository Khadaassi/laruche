"""Envoi des notifications push et règles des rappels programmés.

Chaque notification passe par une **file** (`SentNotification`) : elle est mise en
attente avec son contenu (`enqueue`), puis envoyée par `deliver_pending` — en tâche
de fond juste après un cochage (le cochage n'attend jamais le service push), ou
pendant la tâche planifiée. Un échec du service push est retenté plus tard
(`RETRY_DELAYS`), jusqu'à l'expiration du rappel ; les états sont visibles en admin.
"""

import datetime
import json
import logging
import threading

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.models import F
from django.utils import timezone
from pywebpush import WebPushException, webpush

from .keys import vapid
from .models import Delivery, NotificationPrefs, PushSubscription, SentNotification

logger = logging.getLogger(__name__)

# Délais avant la 2e, 3e et 4e tentative ; au-delà : échec définitif.
RETRY_DELAYS = (
    datetime.timedelta(minutes=5),
    datetime.timedelta(minutes=30),
    datetime.timedelta(hours=2),
)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1

DINNER_FROM = datetime.time(15, 0)
DINNER_UNTIL = datetime.time(20, 0)
REVIEW_FROM = datetime.time(17, 0)
SUNDAY = 6


def prefs_for(user) -> NotificationPrefs:
    return NotificationPrefs.objects.filter(user=user).first() or NotificationPrefs(user=user)


def send_to_user(user, title: str, body: str, url: str = "/", tag: str = "") -> int:
    """Envoie à tous les appareils du parent ; renvoie le nombre d'envois réussis."""
    return _push(user, title=title, body=body, url=url, tag=tag)[0]


def _push(user, title: str, body: str, url: str = "/", tag: str = "") -> tuple[int, int, str]:
    """(envois acceptés, appareils essayés, dernière erreur) pour tous les appareils."""
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})
    claims = {"sub": getattr(settings, "VAPID_SUBJECT", "https://laruche.onrender.com")}
    delivered, tried, error_text = 0, 0, ""
    for sub in PushSubscription.objects.filter(user=user):
        tried += 1
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
                tried -= 1
            else:
                logger.warning("Push refusé (%s) pour %s", status, user.pk)
                error_text = f"Service push : {status}"
            continue
        except Exception:  # réseau : jamais d'erreur visible pour l'utilisateur
            logger.warning("Push impossible pour %s", user.pk, exc_info=True)
            error_text = "Service push injoignable"
            continue
        sub.last_success_at = timezone.now()
        sub.save(update_fields=["last_success_at"])
        delivered += 1
    return delivered, tried, error_text


def end_of_day(day: datetime.date) -> datetime.datetime:
    return timezone.make_aware(
        datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time())
    )


def enqueue(user, kind: str, key: str, *, expires_at=None, **message) -> bool:
    """Met en file au plus une fois par (parent, type, clé) ; True si c'est cet appel."""
    try:
        with transaction.atomic():
            SentNotification.objects.create(
                user=user,
                kind=kind,
                key=key,
                payload=message,
                next_attempt_at=timezone.now(),
                expires_at=expires_at,
            )
    except IntegrityError:
        return False
    return True


def deliver_pending(now=None, user_ids=None) -> dict:
    """Envoie les notifications en attente arrivées à échéance ; sans risque à relancer.

    Chaque ligne est « réservée » par un UPDATE conditionnel (tentatives + 1) : deux
    envois simultanés (tâche de fond et tâche planifiée) ne la traitent pas deux fois.
    """
    now = now or timezone.now()
    counts = {status: 0 for status in Delivery.values}
    pending = SentNotification.objects.filter(status=Delivery.PENDING)
    if user_ids is not None:
        pending = pending.filter(user_id__in=user_ids)
    # Trop tard (dîner après 20 h, journée finie…) : on n'envoie plus.
    counts[Delivery.EXPIRED] = pending.filter(expires_at__lte=now).update(status=Delivery.EXPIRED)
    rows = SentNotification.objects.filter(
        status=Delivery.PENDING, next_attempt_at__lte=now
    ).select_related("user")
    if user_ids is not None:
        rows = rows.filter(user_id__in=user_ids)
    for row in rows:
        claimed = SentNotification.objects.filter(
            pk=row.pk, status=Delivery.PENDING, attempts=row.attempts
        ).update(attempts=F("attempts") + 1, next_attempt_at=None)
        if not claimed:
            continue  # déjà pris par un autre envoi
        attempts = row.attempts + 1
        delivered, tried, error_text = _push(row.user, **row.payload)
        update = {"last_error": error_text[:120]}
        if delivered:
            update.update(status=Delivery.ACCEPTED, delivered_at=timezone.now())
        elif not tried:
            update["status"] = Delivery.NO_DEVICE
        elif attempts >= MAX_ATTEMPTS:
            update["status"] = Delivery.FAILED
        else:
            update.update(status=Delivery.PENDING, next_attempt_at=now + RETRY_DELAYS[attempts - 1])
        SentNotification.objects.filter(pk=row.pk).update(**update)
        counts[update["status"]] += 1
    return counts


def _deliver_in_background(user_ids) -> None:
    try:
        deliver_pending(user_ids=user_ids)
    except Exception:  # jamais d'erreur visible : la tâche planifiée retentera
        logger.exception("Envoi des notifications en attente impossible")
    finally:
        connection.close()  # connexion propre au fil d'exécution


def dispatch_soon(user_ids) -> None:
    """Après la validation de la transaction : envoi en tâche de fond (ou tout de suite
    si `PUSH_INLINE`, pour les tests). La requête n'attend pas le service push."""
    user_ids = list(user_ids)

    def run():
        if getattr(settings, "PUSH_INLINE", False):
            deliver_pending(user_ids=user_ids)
        else:
            threading.Thread(target=_deliver_in_background, args=(user_ids,), daemon=True).start()

    transaction.on_commit(run)


def notify_once(user, kind: str, key: str, **message) -> bool:
    """Met en file (sans doublon) puis demande l'envoi en tâche de fond."""
    queued = enqueue(user, kind, key, **message)
    if queued:
        dispatch_soon([user.pk])
    return queued


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
                expires_at=end_of_day(day),
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
                if prefs_for(parent).dinner and enqueue(
                    parent,
                    "dinner",
                    today.isoformat(),
                    expires_at=timezone.make_aware(datetime.datetime.combine(today, DINNER_UNTIL)),
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
                    if prefs_for(parent).review and enqueue(
                        parent,
                        "review",
                        monday.isoformat(),
                        expires_at=end_of_day(today),
                        title="Revue de la semaine",
                        body="5 minutes pour préparer la semaine qui vient.",
                        url="/revue/",
                        tag="review",
                    ):
                        sent["review"] += 1
    # Nouveaux rappels et nouvelles tentatives des envois précédents en échec.
    sent["delivery"] = deliver_pending(now)
    return sent
