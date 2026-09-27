from django.urls import path

from . import views

app_name = "shopping"

urlpatterns = [
    path("courses/", views.index, name="index"),
    path("courses/envoyer-le-menu/", views.transfer, name="transfer"),
    path("courses/retirer-les-achats/", views.clear, name="clear"),
    path("courses/<int:pk>/fait/", views.toggle, name="toggle"),
    path("courses/<int:pk>/a-la-maison/", views.at_home, name="at_home"),
    path("courses/<int:pk>/remettre/", views.restore, name="restore"),
    path("courses/<int:pk>/modifier/", views.edit, name="edit"),
    path("courses/<int:pk>/supprimer/", views.delete, name="delete"),
]
