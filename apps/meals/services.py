"""Écritures sur les recettes : import depuis la bibliothèque."""

from decimal import Decimal

from django.db import transaction

from .library import BY_KEY
from .models import Recipe, RecipeIngredient
from .units import normalize_name


def family_recipe_names(family) -> set[str]:
    return {
        normalize_name(n) for n in Recipe.objects.for_family(family).values_list("name", flat=True)
    }


@transaction.atomic
def import_library(family, keys) -> list[Recipe]:
    """Copie des recettes de la bibliothèque dans la famille (modifiables ensuite).

    Une recette dont le nom existe déjà dans la famille n'est pas recopiée : on peut
    relancer sans doublon. Clés inconnues ignorées. Renvoie les recettes créées.
    """
    existing = family_recipe_names(family)
    created = []
    for key in keys:
        model = BY_KEY.get(key)
        if model is None or normalize_name(model.name) in existing:
            continue
        recipe = Recipe.objects.create(family=family, name=model.name, prep_minutes=model.minutes)
        RecipeIngredient.objects.bulk_create(
            RecipeIngredient(
                recipe=recipe,
                name=name,
                quantity=Decimal(quantity) if quantity is not None else None,
                unit=unit,
            )
            for name, quantity, unit in model.ingredients
        )
        recipe.replace_steps(model.steps)
        existing.add(normalize_name(model.name))
        created.append(recipe)
    return created
