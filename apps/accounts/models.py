from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Utilisateur personnalisé.

    La connexion se fait par e-mail : à l'inscription, `username` reçoit
    l'e-mail normalisé (minuscules), ce qui garantit aussi son unicité.
    Le rattachement à une famille et le rôle vivent dans
    `families.FamilyMembership` (un compte = une famille).
    """

    @property
    def family(self):
        """Famille du compte, ou None s'il n'est rattaché à aucune."""
        membership = getattr(self, "membership", None)
        return membership.family if membership else None
