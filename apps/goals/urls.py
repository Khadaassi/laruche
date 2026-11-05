from django.urls import path

from . import views

app_name = "goals"

urlpatterns = [
    path("mon-annee/", views.board, name="board"),
    path("mon-annee/objectifs/<int:pk>/", views.detail, name="detail"),
    path("mon-annee/objectifs/<int:pk>/modifier/", views.edit, name="edit"),
    path("mon-annee/objectifs/<int:pk>/note/", views.add_entry, name="add_entry"),
    path("mon-annee/objectifs/<int:pk>/proche/", views.add_contact, name="add_contact"),
    path("mon-annee/pas/<int:pk>/", views.log_step, name="log_step"),
    path("mon-annee/notes/<int:pk>/supprimer/", views.delete_entry, name="delete_entry"),
    path("mon-annee/proches/<int:pk>/nouvelles/", views.contact_done, name="contact_done"),
    path("mon-annee/proches/<int:pk>/supprimer/", views.delete_contact, name="delete_contact"),
]
