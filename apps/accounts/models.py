from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Utilisateur personnalisé, posé dès la Phase 0.

    Vide pour l'instant : il existe pour que les évolutions de la Phase 1
    (rôle parent/enfant, rattachement à une famille) ne nécessitent pas de
    migrer depuis auth.User, opération très coûteuse une fois en production.
    """
