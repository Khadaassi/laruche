from django.contrib import admin

from .models import ChoreSwap, HouseholdChore


class ChoreSwapInline(admin.TabularInline):
    model = ChoreSwap
    extra = 0


@admin.register(HouseholdChore)
class HouseholdChoreAdmin(admin.ModelAdmin):
    list_display = ["title", "assignee", "alternate", "schedule_display", "family"]
    raw_id_fields = ["family", "assignee", "alternate"]
    inlines = [ChoreSwapInline]
