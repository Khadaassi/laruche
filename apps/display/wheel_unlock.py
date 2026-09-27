"""Déverrouillage temporaire de la roue du samedi sur l'écran partagé.

Un parent confirme avec son mot de passe (parent_check, même garde que la
sortie du mode tablette) ; la session de l'écran reçoit alors, pour 10 minutes,
le droit de lancer la roue pour CETTE famille, au nom de ce parent. Rien d'autre
n'est accordé : l'écran garde son privilège « enfant » partout ailleurs.
"""

import datetime

from django.utils import timezone

from apps.accounts.models import User
from apps.families.access import get_membership
from apps.families.models import Role

SESSION_KEY = "saturday_wheel_unlock"
UNLOCK_DURATION = datetime.timedelta(minutes=10)


def grant(request, family, parent) -> None:
    request.session[SESSION_KEY] = {
        "family": family.pk,
        "parent": parent.pk,
        "until": (timezone.now() + UNLOCK_DURATION).isoformat(),
    }


def revoke(request) -> None:
    request.session.pop(SESSION_KEY, None)


def wheel_parent(request):
    """Le parent au nom duquel l'écran peut lancer la roue, ou None.

    Un parent connecté en aperçu n'a pas besoin de confirmer.
    """
    if request.display_device is None:
        membership = get_membership(request.user)
        if membership is not None and membership.is_parent:
            return request.user
    unlock = request.session.get(SESSION_KEY)
    if not unlock or unlock.get("family") != request.family.pk:
        return None
    if datetime.datetime.fromisoformat(unlock["until"]) < timezone.now():
        revoke(request)
        return None
    # Le parent doit toujours être parent de cette famille (révocation, promotion…).
    return User.objects.filter(
        pk=unlock["parent"], membership__family=request.family, membership__role=Role.PARENT
    ).first()
