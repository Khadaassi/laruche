from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "start_time", "end_time", "start_date", "end_date", "family"]
    raw_id_fields = ["family"]
    filter_horizontal = ["people"]
