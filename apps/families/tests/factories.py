"""Fabriques de données de test, partagées par toutes les apps."""

import itertools

from apps.accounts.models import User
from apps.families.models import AvatarColor, Family, Person, Role
from apps.families.services import join_or_create_family

PASSWORD = "mot-de-passe-de-test-solide"
_seq = itertools.count(1)


def make_user(first_name="Alex", email=None):
    n = next(_seq)
    email = email or f"user{n}@example.test"
    return User.objects.create_user(
        username=email, email=email, password=PASSWORD, first_name=first_name
    )


def make_family(name="Famille Test", code=None):
    return Family.objects.create(name=name, invite_code=code or f"TESTCODE{next(_seq)}")


def join(family, first_name="Alex"):
    """Crée un compte et le rattache à `family` via le vrai parcours d'inscription."""
    user = make_user(first_name=first_name)
    join_or_create_family(user=user, invite_code=family.invite_code, family_name=family.name)
    user.refresh_from_db()
    return user


def make_child_profile(family, name="Lina"):
    """Enfant sans compte, comme un parent le crée depuis les réglages."""
    return Person.objects.create(
        family=family, name=name, role=Role.CHILD, avatar_color=AvatarColor.TERRACOTTA
    )
