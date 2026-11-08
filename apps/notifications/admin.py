from django.contrib import admin

from .models import NotificationPrefs, PushSubscription, ScheduledRun, SentNotification


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "last_success_at"]
    raw_id_fields = ["user"]


@admin.register(NotificationPrefs)
class NotificationPrefsAdmin(admin.ModelAdmin):
    list_display = ["user", "dinner", "review", "day_done"]
    raw_id_fields = ["user"]


@admin.register(SentNotification)
class SentNotificationAdmin(admin.ModelAdmin):
    list_display = ["kind", "key", "user", "status", "attempts", "sent_at", "delivered_at"]
    list_filter = ["status", "kind"]
    raw_id_fields = ["user"]


@admin.register(ScheduledRun)
class ScheduledRunAdmin(admin.ModelAdmin):
    list_display = ["name", "last_success_at"]
