from django.apps import AppConfig


class FlyladyConfig(AppConfig):
    """Ménage façon FlyLady : routines, zone de la semaine, 15 minutes par jour."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.flylady"
    label = "flylady"
    verbose_name = "Ménage FlyLady"
