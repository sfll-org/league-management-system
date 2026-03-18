from django.contrib import admin
from .models import EmailTemplate, EmailSend, EmailRecipient, RSVPToken


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'subject_template')
    list_filter = ('template_type',)


class EmailRecipientInline(admin.TabularInline):
    model = EmailRecipient
    extra = 0
    readonly_fields = ('email', 'player', 'delivered', 'opened', 'clicked')


@admin.register(EmailSend)
class EmailSendAdmin(admin.ModelAdmin):
    list_display = ('template', 'sent_by', 'recipient_count', 'status', 'sent_at')
    list_filter = ('status',)
    inlines = [EmailRecipientInline]


@admin.register(RSVPToken)
class RSVPTokenAdmin(admin.ModelAdmin):
    list_display = ('player', 'event_description', 'response', 'responded_at')
    list_filter = ('response',)
    search_fields = ('player__first_name', 'player__last_name')
