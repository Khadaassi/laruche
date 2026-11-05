from django.contrib import admin

from .models import NotificationPrefs, PushSubscription


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "last_success_at"]
    raw_id_fields = ["user"]


@admin.register(NotificationPrefs)
class NotificationPrefsAdmin(admin.ModelAdmin):
    list_display = ["user", "dinner", "review", "day_done"]
    raw_id_fields = ["user"]
