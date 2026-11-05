from django.urls import path

from . import views

app_name = "flylady"

urlpatterns = [
    path("menage/flylady/", views.today, name="today"),
    path("menage/flylady/cocher/", views.toggle, name="toggle"),
    path("reglages/flylady/", views.manage, name="manage"),
]
