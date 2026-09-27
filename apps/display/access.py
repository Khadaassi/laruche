"""Accès « affichage partagé » : jeton d'appareil, sans session par enfant.

Voir .claude/skills/permissions/SKILL.md §3. L'appareil porte seulement la
famille et un privilège « enfant » : il ne donne jamais accès aux vues parent.
"""

import datetime
from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.families.access import get_membership

from .models import SharedDisplayDevice, hash_token

DEVICE_COOKIE = "laruche_display"
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # un an ; révocable côté serveur
# Évite une écriture en base à chaque requête (Neon) : précision suffisante.
LAST_USED_RESOLUTION = datetime.timedelta(minutes=15)


def get_device(request) -> SharedDisplayDevice | None:
    raw = request.COOKIES.get(DEVICE_COOKIE)
    if not raw:
        return None
    device = (
        SharedDisplayDevice.objects.active()
        .select_related("family")
        .filter(token_hash=hash_token(raw))
        .first()
    )
    if device is not None:
        now = timezone.now()
        if device.last_used_at is None or now - device.last_used_at > LAST_USED_RESOLUTION:
            device.last_used_at = now
            device.save(update_fields=["last_used_at"])
    return device


def set_device_cookie(response, raw_token: str) -> None:
    response.set_cookie(
        DEVICE_COOKIE,
        raw_token,
        max_age=DEVICE_COOKIE_MAX_AGE,
        secure=not settings.DEBUG,
        httponly=True,
        samesite="Lax",
    )


def delete_device_cookie(response) -> None:
    response.delete_cookie(DEVICE_COOKIE, samesite="Lax")


def shared_display_required(view):
    """Appareil partagé valide, ou parent connecté (aperçu depuis son compte).

    Pose `request.family` et `request.display_device` (None en aperçu parent).
    Sinon : redirection vers la connexion. Un compte enfant n'y a pas accès
    (il agirait sur les tâches de ses frères et sœurs).
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        device = get_device(request)
        if device is not None:
            request.display_device = device
            request.family = device.family
            return view(request, *args, **kwargs)
        membership = get_membership(request.user)
        if membership is not None and membership.is_parent:
            request.display_device = None
            request.family = membership.family
            return view(request, *args, **kwargs)
        if request.user.is_authenticated:
            raise PermissionDenied("Réservé aux parents ou à un appareil partagé.")
        return redirect_to_login(request.get_full_path())

    return wrapper
