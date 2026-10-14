from django.contrib import admin

from .models import Category, Recurrence, Transaction


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "kind", "parent"]
    list_filter = ["kind"]
    search_fields = ["name", "user__email"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["date", "user", "type", "amount", "payee", "account", "category"]
    list_filter = ["type"]
    search_fields = ["payee", "notes", "user__email"]
    date_hierarchy = "date"


@admin.register(Recurrence)
class RecurrenceAdmin(admin.ModelAdmin):
    list_display = ["user", "frequency", "type", "amount", "next_date", "is_active"]
    list_filter = ["frequency", "type", "is_active"]
