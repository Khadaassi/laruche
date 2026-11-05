from django.urls import path

from . import quick, views

app_name = "core"

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("hors-ligne/", views.offline, name="offline"),
    path("ajout-rapide/", quick.quick_add, name="quick_add"),
]
