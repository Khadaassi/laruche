from django.apps import AppConfig


class MomentsConfig(AppConfig):
    """Moments particuliers : saisons, vendredi, Ramadan, Aïd, anniversaires."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.moments"
    label = "moments"
    verbose_name = "Moments particuliers"
