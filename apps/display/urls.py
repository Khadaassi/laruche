from django.urls import path

from . import views

app_name = "display"

urlpatterns = [
    path("affichage/", views.board, name="board"),
    path(
        "affichage/enfants/<int:person_pk>/taches/<int:task_pk>/fait/",
        views.toggle,
        name="toggle",
    ),
    path(
        "affichage/enfants/<int:person_pk>/menage/<int:chore_pk>/fait/",
        views.toggle_chore,
        name="toggle_chore",
    ),
    path("affichage/semaine/", views.week, name="week"),
    path("affichage/fetes/", views.celebrations, name="celebrations"),
    path("affichage/activer/", views.activate, name="activate"),
    path("affichage/appareils/<int:pk>/revoquer/", views.revoke, name="revoke"),
    path("affichage/quitter/", views.exit_display, name="exit"),
]
