from django.apps import AppConfig


class TasksConfig(AppConfig):
    """Tâches du quotidien par personne et période, et leur validation."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"
    label = "tasks"
    verbose_name = "Tâches"
