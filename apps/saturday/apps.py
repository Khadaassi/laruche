from django.apps import AppConfig


class SaturdayConfig(AppConfig):
    """Roue des activités du samedi : catalogue, tirage, plan du samedi."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.saturday"
    label = "saturday"
    verbose_name = "Samedi"
