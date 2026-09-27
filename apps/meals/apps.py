from django.apps import AppConfig


class MealsConfig(AppConfig):
    """Recettes (ingrédients quantifiés, étapes) et menu de la semaine."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.meals"
    label = "meals"
    verbose_name = "Menu et recettes"
