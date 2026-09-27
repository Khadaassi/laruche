from django.urls import path

from . import views

app_name = "absences"

urlpatterns = [
    path("reglages/absences/", views.manage, name="manage"),
    path("reglages/absences/<int:pk>/supprimer/", views.delete, name="delete"),
]
