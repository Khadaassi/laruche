from django.contrib import admin

from .models import Task, TaskCompletion


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "person", "period", "weekdays_display"]
    list_filter = ["period"]
    list_select_related = ["person"]
    raw_id_fields = ["person"]


@admin.register(TaskCompletion)
class TaskCompletionAdmin(admin.ModelAdmin):
    list_display = ["task", "date", "completed_at"]
    raw_id_fields = ["task", "completed_by"]
