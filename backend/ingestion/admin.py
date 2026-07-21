from django.contrib import admin
from ingestion.models import IngestionJob, IngestionJobLog


class IngestionJobLogInline(admin.TabularInline):
    model = IngestionJobLog
    extra = 0
    readonly_fields = ["level", "message", "created_at"]
    can_delete = False


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = ["id", "original_filename", "uploaded_by", "status", "classroom_id", "file_hash", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["id", "original_filename", "uploaded_by__email", "file_hash", "classroom_id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [IngestionJobLogInline]


@admin.register(IngestionJobLog)
class IngestionJobLogAdmin(admin.ModelAdmin):
    list_display = ["id", "job", "level", "message", "created_at"]
    list_filter = ["level", "created_at"]
    search_fields = ["job__id", "message"]
    readonly_fields = ["id", "job", "level", "message", "created_at"]
