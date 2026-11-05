from django.apps import AppConfig


class HolidaysConfig(AppConfig):
    """Vacances scolaires : mode vacances (tâches essentielles, le reste en bonus)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.holidays"
    label = "holidays"
    verbose_name = "Vacances scolaires"
