from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Notifications push (parents) : dîner non prévu, revue du dimanche, journée terminée."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Notifications"
