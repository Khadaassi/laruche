from django.apps import AppConfig


class ProgressConfig(AppConfig):
    """Suivi au long cours : calendrier du mois, tendance, tâches souvent oubliées.

    Lecture seule, aucun modèle : tout est déduit des validations et des étoiles.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.progress"
    label = "progress"
    verbose_name = "Progrès"
