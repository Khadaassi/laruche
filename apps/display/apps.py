from django.apps import AppConfig


class DisplayConfig(AppConfig):
    """Affichage partagé : tablette commune, appareils autorisés par un parent."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.display"
    label = "display"
    verbose_name = "Affichage partagé"
