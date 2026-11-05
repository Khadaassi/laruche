from django.contrib import admin

from .models import FlyCheck, FlyMission, FlyRoutineItem, FlyZone


class MissionInline(admin.TabularInline):
    model = FlyMission
    extra = 0


@admin.register(FlyZone)
class FlyZoneAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "family"]
    raw_id_fields = ["family"]
    inlines = [MissionInline]


@admin.register(FlyRoutineItem)
class FlyRoutineItemAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "family"]
    raw_id_fields = ["family"]


@admin.register(FlyCheck)
class FlyCheckAdmin(admin.ModelAdmin):
    list_display = ["key", "date", "family"]
    raw_id_fields = ["family"]
