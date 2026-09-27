from django.apps import AppConfig


class StarsConfig(AppConfig):
    """Étoiles des enfants : gagnées (déduites des validations) et dépensées."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stars"
    label = "stars"
    verbose_name = "Étoiles"
