from django.contrib import admin

from .models import SchoolHoliday


@admin.register(SchoolHoliday)
class SchoolHolidayAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date", "family"]
    raw_id_fields = ["family"]
