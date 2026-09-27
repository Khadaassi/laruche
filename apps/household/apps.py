from django.apps import AppConfig


class HouseholdConfig(AppConfig):
    """Ménage : tâches récurrentes de la maison, assignées à un membre."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.household"
    label = "household"
    verbose_name = "Ménage"
