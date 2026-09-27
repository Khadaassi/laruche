from django.apps import AppConfig


class ShoppingConfig(AppConfig):
    """Liste de courses : ingrédients du menu additionnés et produits habituels."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.shopping"
    label = "shopping"
    verbose_name = "Courses"
