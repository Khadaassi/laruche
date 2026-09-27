from django.urls import path

from . import views

app_name = "school"

urlpatterns = [
    path("reglages/ecole/", views.manage, name="manage"),
    path("reglages/ecole/enfants/<int:person_pk>/", views.save_week, name="save_week"),
    path("reglages/ecole/exceptions/", views.add_override, name="add_override"),
    path(
        "reglages/ecole/exceptions/<int:pk>/supprimer/",
        views.delete_override,
        name="delete_override",
    ),
]
