from django.urls import path

from . import views

app_name = "moments"

urlpatterns = [
    path("reglages/moments/", views.manage, name="manage"),
]
