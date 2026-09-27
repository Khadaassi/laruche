from django.contrib import admin

from .models import SchoolDayOverride, SchoolDaySchedule


@admin.register(SchoolDaySchedule)
class SchoolDayScheduleAdmin(admin.ModelAdmin):
    list_display = ["person", "weekday", "lunch", "study"]
    raw_id_fields = ["person"]


@admin.register(SchoolDayOverride)
class SchoolDayOverrideAdmin(admin.ModelAdmin):
    list_display = ["person", "date", "lunch", "study"]
    raw_id_fields = ["person"]
