"""Confirmation par mot de passe d'un parent depuis l'écran partagé.

Un seul mécanisme pour tous les usages (sortir du mode tablette, lancer la roue
du samedi) : même formulaire, même garde de rate-limit (EXIT_DISPLAY), même
cible (l'appareil, ou le compte enfant connecté) — les tentatives s'additionnent
quel que soit l'usage.
"""

from dataclasses import dataclass

from apps.accounts.forms import LoginForm
from apps.core.ratelimit import EXIT_DISPLAY
from apps.families.access import get_membership


@dataclass
class ParentCheck:
    user: object | None  # le parent confirmé, sinon None
    form: LoginForm
    blocked: bool = False


def guard_target(request) -> str:
    """Cible du rate-limit : l'appareil partagé, sinon le compte connecté."""
    device = getattr(request, "display_device", None)
    if device is not None:
        return str(device.pk)
    return f"user-{request.user.pk}"


def check_parent_password(request, family) -> ParentCheck:
    """Vérifie qu'un parent de `family` saisit son mot de passe (POST uniquement).

    Bloqué : le mot de passe n'est même pas vérifié (formulaire vierge).
    """
    if request.method != "POST":
        return ParentCheck(None, LoginForm(request))
    target = guard_target(request)
    if EXIT_DISPLAY.is_blocked(request, target=target):
        return ParentCheck(None, LoginForm(request), blocked=True)
    form = LoginForm(request, data=request.POST)
    if form.is_valid():
        user = form.get_user()
        membership = get_membership(user)
        if membership is not None and membership.is_parent and membership.family_id == family.pk:
            return ParentCheck(user, form)
        form.add_error(None, "Seul un parent de cette famille peut confirmer.")
    EXIT_DISPLAY.record_failure(request, target=target)
    return ParentCheck(None, form)
