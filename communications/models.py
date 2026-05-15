from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class EmailTemplate(TimeStampedModel):
    """Reusable email template for league communications."""
    league = models.ForeignKey(
        'players.League', on_delete=models.CASCADE, related_name='email_templates'
    )
    name = models.CharField(max_length=100)
    subject_template = models.CharField(max_length=500)
    body_template = models.TextField()
    reply_to = models.EmailField(blank=True)
    from_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class EmailLog(TimeStampedModel):
    """Record of an individual email sent to a player/family."""
    player_season = models.ForeignKey(
        'players.PlayerSeason', on_delete=models.CASCADE, related_name='emails'
    )
    template = models.ForeignKey(
        EmailTemplate, on_delete=models.SET_NULL, null=True
    )
    to_address = models.EmailField()
    cc_addresses = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=500)
    body_snapshot = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    bounced = models.BooleanField(default=False)
    bounce_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"Email to {self.to_address} — {self.subject[:50]}"


class RSVP(TimeStampedModel):
    """An RSVP response for an SES session."""
    player_season = models.ForeignKey(
        'players.PlayerSeason', on_delete=models.CASCADE, related_name='rsvps'
    )
    session = models.ForeignKey(
        'tryouts.Session', on_delete=models.CASCADE, related_name='rsvps'
    )
    status = models.CharField(max_length=20, choices=[
        ('attending', 'Attending'),
        ('not_attending', 'Not Attending'),
        ('maybe', 'Maybe'),
    ])
    response_method = models.CharField(max_length=20, default='web')
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"RSVP: {self.player_season} — {self.get_status_display()}"
