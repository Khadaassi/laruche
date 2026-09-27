from django.contrib import admin

from .models import Absence


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ["family", "person", "kind", "start_date", "end_date"]
    raw_id_fields = ["family", "person"]
