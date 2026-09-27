"""Fabriques de données de test, partagées par toutes les apps."""

import itertools

from apps.accounts.models import User
from apps.families.models import AvatarColor, Family, Person, Role
from apps.families.services import join_family

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
    join_family(user=user, invite_code=family.invite_code)
    user.refresh_from_db()
    return user


def make_child_profile(family, name="Lina"):
    """Enfant sans compte, comme un parent le crée depuis les réglages."""
    return Person.objects.create(
        family=family, name=name, role=Role.CHILD, avatar_color=AvatarColor.TERRACOTTA
    )


class SecureClientMixin:
    """HTTPS est forcé hors DEBUG : toutes les requêtes de test passent en secure.

    Vide aussi le cache avant chaque test : les compteurs de rate-limit d'un
    test ne doivent pas bloquer le suivant.
    """

    @classmethod
    def _fixture_setup(cls):  # appelé avant chaque test
        from django.core.cache import cache

        cache.clear()
        super()._fixture_setup()

    def get(self, url, data=None, **kwargs):
        return self.client.get(url, data, secure=True, **kwargs)

    def post(self, url, data=None, **kwargs):
        return self.client.post(url, data or {}, secure=True, **kwargs)

    def htmx_post(self, url, data=None):
        return self.post(url, data, headers={"HX-Request": "true"})
