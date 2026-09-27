from django.apps import AppConfig


class AbsencesConfig(AppConfig):
    """Vacances et absences (malade…) : suspendent les tâches sur une période."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.absences"
    label = "absences"
    verbose_name = "Absences"
