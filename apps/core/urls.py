from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("menu/", views.coming_soon, {"section": "menu"}, name="menu"),
]
