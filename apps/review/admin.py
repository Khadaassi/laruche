from django.contrib import admin

from .models import WeeklyReview


@admin.register(WeeklyReview)
class WeeklyReviewAdmin(admin.ModelAdmin):
    list_display = ["week", "family", "done_at"]
    raw_id_fields = ["family"]
