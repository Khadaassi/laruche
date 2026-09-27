"""Règles métier des familles, hors vues (testables directement)."""

import secrets

from django.db import IntegrityError, transaction

from apps.accounts.models import User, normalize_login_name

from .models import (
    Family,
    FamilyMembership,
    Person,
    Role,
    next_avatar_color,
    normalize_invite_code,
)


def _add_member(user, family: Family) -> FamilyMembership:
    """Premier membre d'une famille = parent ; les suivants entrent en enfant."""
    role = Role.CHILD if family.memberships.exists() else Role.PARENT
    membership = FamilyMembership.objects.create(user=user, family=family, role=role)
    Person.objects.create(
        family=family,
        user=user,
        name=user.first_name,
        role=role,
        avatar_color=next_avatar_color(family),
    )
    return membership


@transaction.atomic
def create_family(*, user, name: str) -> FamilyMembership:
    """Crée une famille dont `user` est le premier parent.

    Le code d'invitation est toujours généré (aléatoire, 10 caractères) :
    il n'est jamais choisi par l'utilisateur, donc jamais devinable.
    """
    for _ in range(5):
        try:
            with transaction.atomic():
                family = Family.objects.create(name=name, invite_code="")
            break
        except IntegrityError:  # collision de code, improbable : on retire
            continue
    else:
        raise RuntimeError("Impossible de générer un code d'invitation unique.")
    # Catalogue de départ de la roue du samedi : la roue n'est jamais vide.
    from apps.saturday.defaults import seed_default_activities

    seed_default_activities(family)
    return _add_member(user, family)


@transaction.atomic
def join_family(*, user, invite_code: str) -> FamilyMembership | None:
    """Rattache `user` à la famille du code ; None si le code est inconnu.

    La ligne de la famille est verrouillée pour que deux inscriptions
    simultanées dans une famille vide ne produisent pas deux « premiers ».
    Les suivants entrent en enfant (un parent les promeut depuis les réglages).
    """
    code = normalize_invite_code(invite_code)
    family = Family.objects.select_for_update().filter(invite_code=code).first() if code else None
    if family is None:
        return None
    return _add_member(user, family)


@transaction.atomic
def promote_to_parent(membership: FamilyMembership) -> None:
    """Passe un membre en parent ; le rôle affiché de sa personne suit."""
    membership.role = Role.PARENT
    membership.save(update_fields=["role"])
    Person.objects.filter(user=membership.user).update(role=Role.PARENT)


def regenerate_invite_code(family: Family) -> None:
    """Nouveau code aléatoire : l'ancien ne permet plus de rejoindre la famille."""
    family.invite_code = ""  # save() en génère un
    family.save(update_fields=["invite_code"])


class LoginNameTaken(Exception):
    """Identifiant déjà utilisé par un autre compte."""


def set_login_name(user, login_name: str) -> None:
    """Donne (ou retire, si vide) l'identifiant court d'un compte.

    Unique sur toute l'application (contrainte en base) : LoginNameTaken sinon.
    Le format est validé par le formulaire (`validate_login_name`).
    """
    value = normalize_login_name(login_name) or None
    if value and User.objects.filter(login_name=value).exclude(pk=user.pk).exists():
        raise LoginNameTaken(value)
    user.login_name = value
    try:
        with transaction.atomic():
            user.save(update_fields=["login_name"])
    except IntegrityError as error:  # pris entre-temps
        raise LoginNameTaken(value) from error


def display_account(family: Family):
    """Compte « écran partagé » de la famille, ou None (au plus un par famille)."""
    membership = (
        FamilyMembership.objects.filter(family=family, role=Role.DISPLAY)
        .select_related("user")
        .first()
    )
    return membership.user if membership else None


@transaction.atomic
def create_display_account(family: Family, *, login_name: str, password: str):
    """Crée le compte « écran partagé » des enfants (identifiant + mot de passe).

    Pas d'e-mail ni de personne : il n'a pas de colonne à lui. Son `username`
    interne est aléatoire ; on se connecte avec l'identifiant. Un seul par famille.
    """
    Family.objects.select_for_update().get(pk=family.pk)
    if display_account(family) is not None:
        raise ValueError("Cette famille a déjà un compte écran partagé.")
    value = normalize_login_name(login_name)
    if User.objects.filter(login_name=value).exists():
        raise LoginNameTaken(value)
    user = User.objects.create_user(
        username=f"ecran-partage-{secrets.token_hex(8)}",
        password=password,
        first_name="Écran partagé",
        login_name=value,
    )
    FamilyMembership.objects.create(user=user, family=family, role=Role.DISPLAY)
    return user
