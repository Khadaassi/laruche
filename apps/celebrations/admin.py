from django.contrib import admin

from .models import Celebration, CelebrationTodo, GiftItem, RecipeIdea


class TodoInline(admin.TabularInline):
    model = CelebrationTodo
    extra = 0
    raw_id_fields = ["assignee"]


class GiftInline(admin.TabularInline):
    model = GiftItem
    extra = 0
    raw_id_fields = ["recipient", "buyer"]


class RecipeInline(admin.TabularInline):
    model = RecipeIdea
    extra = 0


@admin.register(Celebration)
class CelebrationAdmin(admin.ModelAdmin):
    list_display = ["name", "date", "family"]
    raw_id_fields = ["family"]
    inlines = [TodoInline, GiftInline, RecipeInline]
