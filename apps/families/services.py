"""Règles métier des familles, hors vues (testables directement)."""

from django.db import IntegrityError, transaction

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
