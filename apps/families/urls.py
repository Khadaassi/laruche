from django.urls import path

from . import views

app_name = "families"

urlpatterns = [
    path("reglages/", views.settings_page, name="settings"),
    path("reglages/enfants/ajouter/", views.add_child, name="add_child"),
    path("reglages/membres/<int:pk>/promouvoir/", views.promote, name="promote"),
    path("reglages/code/regenerer/", views.regenerate_code, name="regenerate_code"),
    path(
        "reglages/comptes/<int:user_pk>/identifiant/",
        views.update_login_name,
        name="update_login_name",
    ),
    path("reglages/ecran-partage/compte/", views.create_display, name="create_display"),
    path("reglages/ecran-partage/compte/supprimer/", views.delete_display, name="delete_display"),
]
