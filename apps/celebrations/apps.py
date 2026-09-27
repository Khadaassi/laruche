from django.apps import AppConfig


class CelebrationsConfig(AppConfig):
    """Fêtes (Aïd, anniversaires…) : préparatifs, cadeaux, idées de recettes."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.celebrations"
    label = "celebrations"
    verbose_name = "Fêtes"
