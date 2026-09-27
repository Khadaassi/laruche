from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Comptes utilisateurs et authentification."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
