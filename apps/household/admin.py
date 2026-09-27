from django.contrib import admin

from .models import HouseholdChore


@admin.register(HouseholdChore)
class HouseholdChoreAdmin(admin.ModelAdmin):
    list_display = ["title", "assignee", "schedule_display", "family"]
    raw_id_fields = ["family", "assignee"]
