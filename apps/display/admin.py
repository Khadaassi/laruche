from django.contrib import admin

from .models import SharedDisplayDevice


@admin.register(SharedDisplayDevice)
class SharedDisplayDeviceAdmin(admin.ModelAdmin):
    list_display = ["name", "family", "created_at", "last_used_at", "revoked_at"]
    exclude = ["token_hash"]
    raw_id_fields = ["family", "created_by"]
