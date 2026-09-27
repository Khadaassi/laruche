from django.contrib import admin

from .models import MealSlot, Recipe, RecipeIngredient, RecipeStep


class IngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0


class StepInline(admin.TabularInline):
    model = RecipeStep
    extra = 0


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["name", "prep_minutes", "is_favorite", "family"]
    raw_id_fields = ["family"]
    inlines = [IngredientInline, StepInline]


@admin.register(MealSlot)
class MealSlotAdmin(admin.ModelAdmin):
    list_display = ["date", "meal", "kind", "recipe", "note", "family"]
    raw_id_fields = ["family", "recipe"]
