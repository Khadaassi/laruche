from django.contrib import admin

from .models import Goal, Step


class StepInline(admin.TabularInline):
    model = Step
    extra = 0


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["title", "year", "user"]
    raw_id_fields = ["user"]
    inlines = [StepInline]
