from django.urls import path

from . import views

app_name = "saturday"

urlpatterns = [
    path("samedi/", views.page, name="page"),
    path("samedi/tourner/", views.spin, name="spin"),
    path("samedi/<int:pk>/valider/", views.validate, name="validate"),
    path("samedi/<int:pk>/fait/", views.done, name="done"),
    path("samedi/<int:pk>/annuler/", views.cancel_plan, name="cancel"),
    path("reglages/activites/", views.catalog, name="catalog"),
    path("reglages/activites/<int:pk>/", views.edit_activity, name="edit_activity"),
    path("reglages/activites/<int:pk>/supprimer/", views.delete_activity, name="delete_activity"),
]
