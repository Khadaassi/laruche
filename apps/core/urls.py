from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("semaine/", views.coming_soon, {"section": "week"}, name="week"),
    path("menu/", views.coming_soon, {"section": "menu"}, name="menu"),
    path("courses/", views.coming_soon, {"section": "shopping"}, name="shopping"),
]
