"""Contrôles d'accès centralisés (voir .claude/skills/permissions/SKILL.md).

La famille de la requête vient toujours du serveur : de l'appartenance du
compte connecté (ici) ou du jeton d'appareil partagé (apps.display.access).
Jamais d'un paramètre d'URL, d'un champ caché ou d'un en-tête.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import FamilyMembership, Person


def get_membership(user) -> FamilyMembership | None:
    if not user.is_authenticated:
        return None
    try:
        return user.membership
    except FamilyMembership.DoesNotExist:
        return None


def family_member_required(view):
    """Compte connecté ET membre d'une famille.

    Pose `request.membership`, `request.family` et `request.person` (la
    personne du compte, ou None). Un compte sans famille (superutilisateur
    de l'équipe, par exemple) reçoit un 403.
    """

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        membership = get_membership(request.user)
        if membership is None:
            raise PermissionDenied("Ce compte n'est rattaché à aucune famille.")
        request.membership = membership
        request.family = membership.family
        request.person = (
            Person.objects.for_family(membership.family).filter(user=request.user).first()
        )
        return view(request, *args, **kwargs)

    return wrapper


def parent_required(view):
    """Membre de la famille avec le rôle parent ; sinon 403."""

    @family_member_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.membership.is_parent:
            raise PermissionDenied("Réservé aux parents.")
        return view(request, *args, **kwargs)

    return wrapper
