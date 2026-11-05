from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.EmailLoginView.as_view(), name="login"),
    path("inscription/", views.signup, name="signup"),
    # POST uniquement (Django 5) : pas de déconnexion par simple lien.
    path("deconnexion/", LogoutView.as_view(), name="logout"),
    path(
        "mot-de-passe/<uidb64>/<token>/",
        views.ResetPasswordView.as_view(),
        name="password_reset",
    ),
    path(
        "mot-de-passe/termine/", views.ResetPasswordDoneView.as_view(), name="password_reset_done"
    ),
    path(
        "reglages/mon-mot-de-passe/",
        login_required(views.ChangePasswordView.as_view()),
        name="password_change",
    ),
]
