import re

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

# Identifiant court : lettres minuscules, chiffres, point, tiret, tiret bas ; 2 à 30 signes.
LOGIN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,29}$")


def normalize_login_name(raw: str) -> str:
    return (raw or "").strip().lower()


def validate_login_name(value: str) -> None:
    if not LOGIN_NAME_RE.match(value or ""):
        raise ValidationError(
            "De 2 à 30 caractères : lettres sans accent, chiffres, point, tiret ou tiret bas."
        )


class User(AbstractUser):
    """Utilisateur personnalisé.

    La connexion se fait par e-mail **ou par identifiant court** (`login_name`,
    facultatif : « khadija », « enfants »). À l'inscription, `username` reçoit
    l'e-mail normalisé (minuscules), ce qui garantit aussi son unicité ; un compte
    « écran partagé » n'a pas d'e-mail et reçoit un `username` interne.
    Le rattachement à une famille et le rôle vivent dans
    `families.FamilyMembership` (un compte = une famille).
    """

    login_name = models.CharField(
        "identifiant",
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        validators=[validate_login_name],
        help_text="Identifiant court de connexion, à la place de l'e-mail.",
    )

    @property
    def family(self):
        """Famille du compte, ou None s'il n'est rattaché à aucune."""
        membership = getattr(self, "membership", None)
        return membership.family if membership else None
