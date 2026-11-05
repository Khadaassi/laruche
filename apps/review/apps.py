from django.apps import AppConfig


class ReviewConfig(AppConfig):
    """Revue du dimanche : 5 minutes guidées pour préparer la semaine qui vient."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.review"
    label = "review"
    verbose_name = "Revue de la semaine"
