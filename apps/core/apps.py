from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Briques transverses : santé, gabarits de base, utilitaires partagés."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
