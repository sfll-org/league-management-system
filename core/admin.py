from django.contrib import admin

from .models import AuditLog, ImportFlag, ImportRun


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'entity_type', 'entity_id')
    list_filter = ('action', 'entity_type')
    search_fields = ('entity_type', 'action', 'user__email')
    readonly_fields = ('timestamp', 'user', 'action', 'entity_type', 'entity_id', 'details', 'ip_address')
    date_hierarchy = 'timestamp'


class ImportFlagInline(admin.TabularInline):
    model = ImportFlag
    extra = 0
    readonly_fields = ('flag_type', 'player_season', 'details')


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'league', 'status', 'total_rows', 'new_players', 'errors', 'started_at')
    list_filter = ('status', 'triggered_by', 'league')
    readonly_fields = ('started_at',)
    inlines = [ImportFlagInline]


@admin.register(ImportFlag)
class ImportFlagAdmin(admin.ModelAdmin):
    list_display = ('id', 'import_run', 'flag_type', 'resolved', 'resolved_by')
    list_filter = ('flag_type', 'resolved')
    search_fields = ('details',)
