from django.apps import AppConfig


class GoalsConfig(AppConfig):
    """« Mon année » : objectifs personnels (vision board), privés à chaque parent."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.goals"
    label = "goals"
    verbose_name = "Mon année"
