from django.urls import path

from . import views

app_name = "review"

urlpatterns = [
    path("revue/", views.week, name="week"),
    path("revue/terminee/", views.done, name="done"),
]
