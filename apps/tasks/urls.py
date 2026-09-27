from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.home, name="home"),
    path("taches/<int:pk>/fait/", views.toggle, name="toggle"),
    path("reglages/taches/", views.manage, name="manage"),
    path("reglages/taches/<int:pk>/modifier/", views.edit, name="edit"),
    path("reglages/taches/<int:pk>/monter/", views.move, {"direction": "monter"}, name="move_up"),
    path(
        "reglages/taches/<int:pk>/descendre/",
        views.move,
        {"direction": "descendre"},
        name="move_down",
    ),
    path("reglages/taches/<int:pk>/supprimer/", views.delete, name="delete"),
]
