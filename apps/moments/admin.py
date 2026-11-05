from django.contrib import admin

from .models import MomentSettings, PersonBirthday


@admin.register(MomentSettings)
class MomentSettingsAdmin(admin.ModelAdmin):
    list_display = ["family", "hijri_shift", "eid_days", "ramadan_light"]
    raw_id_fields = ["family"]


@admin.register(PersonBirthday)
class PersonBirthdayAdmin(admin.ModelAdmin):
    list_display = ["person", "birth_date"]
    raw_id_fields = ["person"]
