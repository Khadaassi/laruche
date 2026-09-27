from django.urls import path, register_converter

from . import views
from .models import Meal


class MealConverter:
    """Créneau dans l'URL, en français : /menu/2026-09-28/diner/."""

    regex = "dejeuner|diner"
    slugs = {Meal.LUNCH: "dejeuner", Meal.DINNER: "diner"}

    def to_python(self, value):
        return next(meal for meal, slug in self.slugs.items() if slug == value)

    def to_url(self, value):
        return self.slugs[Meal(value)]


register_converter(MealConverter, "meal")

app_name = "meals"

urlpatterns = [
    path("menu/", views.menu, name="menu"),
    path("menu/<str:day>/<meal:meal>/", views.slot_edit, name="slot_edit"),
    path("recettes/", views.recipes, name="recipes"),
    path("recettes/<int:pk>/", views.recipe_detail, name="recipe_detail"),
    path("recettes/<int:pk>/modifier/", views.recipe_edit, name="recipe_edit"),
    path("recettes/<int:pk>/favori/", views.recipe_favorite, name="recipe_favorite"),
    path("recettes/<int:pk>/supprimer/", views.recipe_delete, name="recipe_delete"),
    path("recettes/<int:pk>/ingredients/ajouter/", views.ingredient_add, name="ingredient_add"),
    path(
        "recettes/ingredients/<int:pk>/supprimer/",
        views.ingredient_delete,
        name="ingredient_delete",
    ),
]
