from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("reglages/notifications/", views.manage, name="manage"),
    path("notifications/abonnement/", views.subscribe, name="subscribe"),
    path("notifications/desabonnement/", views.unsubscribe, name="unsubscribe"),
    path("notifications/test/", views.test, name="test"),
    path("taches-planifiees/", views.cron, name="cron"),
    # Ancienne adresse, gardée pour les appels déjà programmés.
    path("taches-planifiees/notifications/", views.cron),
]
