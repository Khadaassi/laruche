from django.contrib import admin

from .models import ShoppingItem, ShoppingTransfer


@admin.register(ShoppingItem)
class ShoppingItemAdmin(admin.ModelAdmin):
    list_display = ["name", "quantity", "unit", "origin", "status", "recurring", "family"]
    list_filter = ["origin", "status"]
    raw_id_fields = ["family"]


@admin.register(ShoppingTransfer)
class ShoppingTransferAdmin(admin.ModelAdmin):
    list_display = ["family", "week", "transferred_at"]
    raw_id_fields = ["family"]
