"""Accès « affichage partagé » : jeton d'appareil, sans session par enfant.

Voir .claude/skills/permissions/SKILL.md §3. L'appareil porte seulement la
famille et un privilège « enfant » : il ne donne jamais accès aux vues parent.
Un compte enfant passe par le même écran (seul chemin d'accès enfant).
"""

import datetime
from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.families.access import get_membership
from apps.families.models import Person

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
    """Seul chemin d'accès « enfant » : l'écran partagé, toutes les colonnes.

    Accès : appareil partagé valide, parent connecté (aperçu), compte
    « écran partagé » ou compte enfant connecté. Pose `request.family`,
    `request.display_device` (None hors appareil), `request.display_account`
    (vrai pour le compte « écran partagé ») et `request.tickable_person_id` :
    - None → toutes les colonnes sont cochables (appareil, compte écran partagé, parent) ;
    - pk de sa personne → un compte enfant ne coche que sa propre colonne.
    Anonyme : redirection vers la connexion.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        device = get_device(request)
        if device is not None:
            request.display_device = device
            request.display_account = False
            request.family = device.family
            request.tickable_person_id = None
            return view(request, *args, **kwargs)
        membership = get_membership(request.user)
        if membership is None:
            if request.user.is_authenticated:
                raise PermissionDenied("Ce compte n'est rattaché à aucune famille.")
            return redirect_to_login(request.get_full_path())
        request.display_device = None
        request.display_account = membership.is_display
        request.family = membership.family
        if membership.is_parent or membership.is_display:
            request.tickable_person_id = None
        else:
            own = Person.objects.for_family(membership.family).filter(user=request.user).first()
            # Sans personne liée (cas anormal), aucune colonne n'est cochable.
            request.tickable_person_id = own.pk if own else 0
        return view(request, *args, **kwargs)

    return wrapper


def can_tick(request, person) -> bool:
    """La colonne de `person` est-elle cochable par ce visiteur ?"""
    return request.tickable_person_id is None or request.tickable_person_id == person.pk
