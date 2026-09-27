from django.apps import AppConfig


class FamiliesConfig(AppConfig):
    """Familles, appartenance des comptes et personnes affichées."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.families"
    label = "families"
    verbose_name = "Familles"
