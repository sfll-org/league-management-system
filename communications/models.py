import uuid

from django.db import models
from django.conf import settings

from core.models import TimeStampedModel


class EmailTemplate(TimeStampedModel):
    """Reusable email template for league communications."""

    class TemplateType(models.TextChoices):
        TRYOUT_REMINDER = 'tryout_reminder', 'Tryout Reminder'
        TEAM_ASSIGNMENT = 'team_assignment', 'Team Assignment'
        PRACTICE_SCHEDULE = 'practice_schedule', 'Practice Schedule'
        GENERAL = 'general', 'General'
        RSVP_REQUEST = 'rsvp_request', 'RSVP Request'

    name = models.CharField(max_length=200)
    subject_template = models.CharField(max_length=300)
    body_template = models.TextField()
    template_type = models.CharField(
        max_length=30,
        choices=TemplateType.choices,
        default=TemplateType.GENERAL,
    )

    def __str__(self):
        return self.name


class EmailSend(TimeStampedModel):
    """Record of a batch email send."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sends',
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='email_sends',
    )
    recipient_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.template} — {self.sent_at or "not sent"}'


class EmailRecipient(models.Model):
    """Individual recipient within an email send."""
    send = models.ForeignKey(
        EmailSend,
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    email = models.EmailField()
    player = models.ForeignKey(
        'players.Player',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_recipients',
    )
    delivered = models.BooleanField(default=False)
    opened = models.BooleanField(default=False)
    clicked = models.BooleanField(default=False)

    def __str__(self):
        return self.email


class RSVPToken(TimeStampedModel):
    """Tokenized RSVP link for a player/event."""

    class Response(models.TextChoices):
        YES = 'yes', 'Yes'
        NO = 'no', 'No'
        MAYBE = 'maybe', 'Maybe'
        PENDING = 'pending', 'Pending'

    player = models.ForeignKey(
        'players.Player',
        on_delete=models.CASCADE,
        related_name='rsvp_tokens',
    )
    event_description = models.CharField(max_length=300)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    response = models.CharField(
        max_length=10,
        choices=Response.choices,
        default=Response.PENDING,
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'RSVP: {self.player} — {self.event_description} ({self.get_response_display()})'
