from django.urls import path

from . import views

app_name = "progress"

urlpatterns = [
    path("progres/", views.overview, name="overview"),
]
