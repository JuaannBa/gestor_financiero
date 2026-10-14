from django.contrib import admin

from .models import Budget


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ["user", "category", "year", "month", "amount"]
    list_filter = ["year", "month"]
