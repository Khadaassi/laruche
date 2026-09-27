"""Règles métier des familles, hors vues (testables directement)."""

from django.db import IntegrityError, transaction

from .models import Family, FamilyMembership, Person, Role, next_avatar_color


@transaction.atomic
def join_or_create_family(*, user, invite_code: str, family_name: str = "") -> FamilyMembership:
    """Rattache `user` à la famille du code, ou la crée si le code est inconnu.

    Le premier membre d'une famille devient parent ; les suivants entrent en
    enfant (un parent les promeut ensuite depuis les réglages). La ligne de la
    famille est verrouillée pour que deux inscriptions simultanées ne
    produisent pas deux « premiers » parents.
    L'appelant a déjà normalisé le code et vérifié qu'un nom est fourni en
    cas de création (voir accounts.forms.SignupForm).
    """
    family = Family.objects.select_for_update().filter(invite_code=invite_code).first()
    if family is None:
        try:
            with transaction.atomic():
                family = Family.objects.create(name=family_name, invite_code=invite_code)
        except IntegrityError:
            # Créée entre-temps par une inscription concurrente : on la rejoint.
            family = Family.objects.select_for_update().get(invite_code=invite_code)

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
def promote_to_parent(membership: FamilyMembership) -> None:
    """Passe un membre en parent ; le rôle affiché de sa personne suit."""
    membership.role = Role.PARENT
    membership.save(update_fields=["role"])
    Person.objects.filter(user=membership.user).update(role=Role.PARENT)


def regenerate_invite_code(family: Family) -> None:
    """Nouveau code aléatoire : l'ancien ne permet plus de rejoindre la famille."""
    family.invite_code = ""  # save() en génère un
    family.save(update_fields=["invite_code"])
