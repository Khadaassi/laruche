from django.contrib import admin

from .models import DayStar, StarDebit, StarOpeningBalance, StarSpend, TierCelebration


class DebitInline(admin.TabularInline):
    model = StarDebit
    extra = 0
    raw_id_fields = ["person"]


@admin.register(StarSpend)
class StarSpendAdmin(admin.ModelAdmin):
    list_display = ["reason", "total", "family", "created_at"]
    raw_id_fields = ["family"]
    inlines = [DebitInline]


@admin.register(TierCelebration)
class TierCelebrationAdmin(admin.ModelAdmin):
    list_display = ["person", "tier", "updated_at"]
    raw_id_fields = ["person"]


@admin.register(DayStar)
class DayStarAdmin(admin.ModelAdmin):
    list_display = ["person", "date", "celebrated", "created_at"]
    raw_id_fields = ["person"]


@admin.register(StarOpeningBalance)
class StarOpeningBalanceAdmin(admin.ModelAdmin):
    list_display = ["person", "amount", "reason", "created_at"]
    raw_id_fields = ["person"]
