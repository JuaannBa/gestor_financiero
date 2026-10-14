from django.contrib import admin

from .models import ImportBatch


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ["file_name", "user", "status", "created_count", "skipped_count", "created_at"]
    list_filter = ["status"]
    search_fields = ["file_name", "user__email"]
