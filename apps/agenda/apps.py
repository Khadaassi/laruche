from django.apps import AppConfig


class AgendaConfig(AppConfig):
    """Rendez-vous et activités à heure fixe (dentiste, foot…), grille du semainier."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agenda"
    label = "agenda"
    verbose_name = "Agenda"
