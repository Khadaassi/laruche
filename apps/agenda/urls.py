from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("semaine/rendez-vous/ajouter/", views.add, name="add"),
    path("semaine/rendez-vous/<int:pk>/", views.edit, name="edit"),
    path("semaine/rendez-vous/<int:pk>/supprimer/", views.delete, name="delete"),
]
