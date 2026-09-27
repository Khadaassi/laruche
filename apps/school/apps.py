from django.apps import AppConfig


class SchoolConfig(AppConfig):
    """Journée d'école de chaque enfant : midi (cantine, sandwich/APC…) et étude."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.school"
    label = "school"
    verbose_name = "École"
