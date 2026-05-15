from django.contrib import admin

from .models import EmailLog, EmailTemplate, RSVP


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'league', 'subject_template', 'is_active')
    list_filter = ('league', 'is_active')
    search_fields = ('name', 'subject_template')


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('to_address', 'subject', 'sent_at', 'sent_by', 'bounced')
    list_filter = ('bounced', 'sent_at')
    search_fields = ('to_address', 'subject')
    readonly_fields = ('sent_at',)
    date_hierarchy = 'sent_at'


@admin.register(RSVP)
class RSVPAdmin(admin.ModelAdmin):
    list_display = ('player_season', 'session', 'status', 'response_method', 'created_at')
    list_filter = ('status', 'response_method')
    search_fields = (
        'player_season__player__first_name',
        'player_season__player__last_name',
    )
