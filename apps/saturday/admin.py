from django.contrib import admin

from .models import SaturdayActivity, SaturdayPlan


@admin.register(SaturdayActivity)
class SaturdayActivityAdmin(admin.ModelAdmin):
    list_display = ["name", "season", "place", "is_free", "star_cost", "last_done_on", "family"]
    list_filter = ["season", "place"]
    raw_id_fields = ["family"]


@admin.register(SaturdayPlan)
class SaturdayPlanAdmin(admin.ModelAdmin):
    list_display = ["date", "activity_name", "status", "spins", "family"]
    raw_id_fields = ["family", "activity", "star_spend", "created_by"]
