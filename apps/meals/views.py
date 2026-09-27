"""Menu de la semaine et recettes, côté parent : tout est réservé aux parents
et scopé par famille.

Les enfants voient le menu en lecture seule sur l'écran partagé
(apps.display.views.menu). Ils n'ont ni les recettes ni les courses.
"""

import datetime

from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.families.access import parent_required
from apps.household.models import monday_of
from apps.household.views import WEEK_PARAM, requested_monday

from .forms import IngredientForm, MealSlotForm, RecipeForm
from .models import MealSlot, Recipe, RecipeIngredient
from .week import build_menu_week

FAVORITES_PARAM = "favoris"


def _recipe(request, pk):
    return get_object_or_404(Recipe.objects.for_family(request.family), pk=pk)


def _menu_url(date: datetime.date) -> str:
    return f"{reverse('meals:menu')}?{WEEK_PARAM}={monday_of(date).isoformat()}"


# --- Menu de la semaine -----------------------------------------------------


@require_GET
@parent_required
def menu(request):
    """Menu de la semaine : déjeuner et dîner de chaque jour."""
    return render(
        request,
        "parent/menu.html",
        {
            "nav_active": "kitchen",
            "kitchen_tab": "menu",
            "has_recipes": Recipe.objects.for_family(request.family).exists(),
            **build_menu_week(request.family, requested_monday(request)),
        },
    )


@require_http_methods(["GET", "POST"])
@parent_required
def slot_edit(request, day, meal):
    """Choisir le repas d'un créneau : recette, repas libre, ou rien."""
    try:
        date = datetime.date.fromisoformat(day)
    except ValueError as error:
        raise Http404 from error
    slot = MealSlot.objects.for_family(request.family).filter(date=date, meal=meal).first()
    form = MealSlotForm(request.POST or None, family=request.family, slot=slot)
    if request.method == "POST" and form.is_valid():
        form.save(request.family, date, meal)
        return redirect(_menu_url(date))
    return render(
        request,
        "parent/meal_slot_edit.html",
        {
            "nav_active": "kitchen",
            "form": form,
            "date": date,
            "meal": meal,
            "menu_url": _menu_url(date),
        },
        status=400 if form.is_bound and form.errors else 200,
    )


# --- Recettes ---------------------------------------------------------------


@require_http_methods(["GET", "POST"])
@parent_required
def recipes(request):
    """Liste des recettes (favoris d'abord, filtre « Favoris ») et création."""
    form = RecipeForm(request.POST or None, family=request.family)
    if request.method == "POST" and form.is_valid():
        recipe = form.save()
        return redirect("meals:recipe_detail", pk=recipe.pk)
    favorites_only = request.GET.get(FAVORITES_PARAM) == "1"
    # order_by explicite : Meta.ordering est ignoré sur une requête agrégée.
    recipe_list = (
        Recipe.objects.for_family(request.family)
        .annotate(ingredient_count=Count("ingredients"))
        .order_by(*Recipe._meta.ordering)
    )
    if favorites_only:
        recipe_list = recipe_list.filter(is_favorite=True)
    return render(
        request,
        "parent/recipes.html",
        {
            "nav_active": "kitchen",
            "kitchen_tab": "recipes",
            "form": form,
            "recipes": recipe_list,
            "favorites_only": favorites_only,
        },
        status=400 if form.is_bound and form.errors else 200,
    )


def _detail(request, recipe, edit_form=None, ingredient_form=None, status=200):
    return render(
        request,
        "parent/recipe_detail.html",
        {
            "nav_active": "kitchen",
            "recipe": recipe,
            "ingredients": recipe.ingredients.all(),
            "steps": recipe.steps.all(),
            "edit_form": edit_form or RecipeForm(instance=recipe, family=request.family),
            "ingredient_form": ingredient_form or IngredientForm(),
        },
        status=status,
    )


@require_GET
@parent_required
def recipe_detail(request, pk):
    return _detail(request, _recipe(request, pk))


@require_POST
@parent_required
def recipe_edit(request, pk):
    recipe = _recipe(request, pk)
    form = RecipeForm(request.POST, instance=recipe, family=request.family)
    if form.is_valid():
        form.save()
        return redirect("meals:recipe_detail", pk=pk)
    return _detail(request, recipe, edit_form=form, status=400)


@require_POST
@parent_required
def recipe_favorite(request, pk):
    """Ajoute ou retire des favoris (état fixé par le formulaire, idempotent)."""
    recipe = _recipe(request, pk)
    recipe.is_favorite = request.POST.get("favorite") == "on"
    recipe.save(update_fields=["is_favorite"])
    return redirect("meals:recipe_detail", pk=pk)


@require_http_methods(["GET", "POST"])
@parent_required
def recipe_delete(request, pk):
    """Confirmation sur une page dédiée : la recette quitte aussi le menu."""
    recipe = _recipe(request, pk)
    if request.method == "POST":
        recipe.delete()
        return redirect("meals:recipes")
    return render(
        request,
        "parent/recipe_delete.html",
        {
            "nav_active": "kitchen",
            "recipe": recipe,
            "planned": recipe.meal_slots.order_by("date", "-meal"),
        },
    )


@require_POST
@parent_required
def ingredient_add(request, pk):
    recipe = _recipe(request, pk)
    form = IngredientForm(request.POST, instance=RecipeIngredient(recipe=recipe))
    if form.is_valid():
        form.save()
        return redirect("meals:recipe_detail", pk=pk)
    return _detail(request, recipe, ingredient_form=form, status=400)


@require_POST
@parent_required
def ingredient_delete(request, pk):
    ingredient = get_object_or_404(RecipeIngredient.objects.for_family(request.family), pk=pk)
    ingredient.delete()
    return redirect("meals:recipe_detail", pk=ingredient.recipe_id)
