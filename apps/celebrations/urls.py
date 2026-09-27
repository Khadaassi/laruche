from django.urls import path, register_converter

from . import views


class ItemKindConverter:
    """Seuls les trois types de sous-éléments existent dans les URL."""

    regex = "preparatifs|cadeaux|recettes"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(ItemKindConverter, "item_kind")

app_name = "celebrations"

urlpatterns = [
    path("fetes/", views.index, name="index"),
    path("fetes/<int:pk>/", views.detail, name="detail"),
    path("fetes/<int:pk>/modifier/", views.edit, name="edit"),
    path("fetes/<int:pk>/supprimer/", views.delete, name="delete"),
    path("fetes/<int:pk>/<item_kind:kind>/ajouter/", views.add_item, name="add_item"),
    path("fetes/<item_kind:kind>/<int:pk>/fait/", views.toggle_item, name="toggle_item"),
    path("fetes/<item_kind:kind>/<int:pk>/supprimer/", views.delete_item, name="delete_item"),
]
