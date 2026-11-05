from django.urls import path

from . import views

app_name = "holidays"

urlpatterns = [
    path("reglages/vacances-scolaires/", views.manage, name="manage"),
    path("reglages/vacances-scolaires/zone-b/", views.prefill, name="prefill"),
    path("reglages/vacances-scolaires/<int:pk>/supprimer/", views.delete, name="delete"),
]
