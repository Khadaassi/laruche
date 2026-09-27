from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.home, name="home"),
    path("taches/<int:pk>/fait/", views.toggle, name="toggle"),
    path("reglages/taches/", views.manage, name="manage"),
    path("reglages/taches/<int:pk>/supprimer/", views.delete, name="delete"),
]
