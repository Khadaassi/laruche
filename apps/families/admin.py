from django.contrib import admin

from .models import Family, FamilyMembership, Person


class MembershipInline(admin.TabularInline):
    model = FamilyMembership
    extra = 0
    raw_id_fields = ["user"]


class PersonInline(admin.TabularInline):
    model = Person
    extra = 0
    raw_id_fields = ["user"]


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]
    inlines = [MembershipInline, PersonInline]
