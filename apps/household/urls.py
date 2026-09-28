from django.urls import path

from . import views

app_name = "household"

urlpatterns = [
    path("semaine/", views.week, name="week"),
    path(
        "semaine/menage/<int:pk>/<str:day>/fait/",
        views.toggle,
        name="toggle",
    ),
    path("reglages/menage/", views.manage, name="manage"),
    path("reglages/menage/echanger/", views.swap, name="swap"),
    path("reglages/menage/<int:pk>/supprimer/", views.delete, name="delete"),
]
