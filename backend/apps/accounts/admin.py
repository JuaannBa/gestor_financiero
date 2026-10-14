from django.contrib import admin

from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "type", "currency", "opening_balance", "is_archived"]
    list_filter = ["type", "is_archived", "currency"]
    search_fields = ["name", "user__email"]
