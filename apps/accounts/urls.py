from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.EmailLoginView.as_view(), name="login"),
    path("inscription/", views.signup, name="signup"),
    # POST uniquement (Django 5) : pas de déconnexion par simple lien.
    path("deconnexion/", LogoutView.as_view(), name="logout"),
]
