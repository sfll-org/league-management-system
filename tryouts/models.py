import uuid

from django.db import models
from django.conf import settings

from core.models import TimeStampedModel


class TryoutSession(TimeStampedModel):
    """A scheduled tryout session for a division."""

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'

    name = models.CharField(max_length=200)
    division = models.ForeignKey(
        'players.Division',
        on_delete=models.CASCADE,
        related_name='tryout_sessions',
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )

    class Meta:
        ordering = ['-date', 'start_time']

    def __str__(self):
        return f'{self.name} — {self.date}'


class Station(TimeStampedModel):
    """An evaluation station within a tryout session."""
    session = models.ForeignKey(
        TryoutSession,
        on_delete=models.CASCADE,
        related_name='stations',
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField(default=0)
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stations',
    )

    class Meta:
        ordering = ['session', 'order']

    def __str__(self):
        return f'{self.name} (Session: {self.session.name})'


class CheckIn(TimeStampedModel):
    """Tracks player check-in at a tryout session."""

    class Status(models.TextChoices):
        CHECKED_IN = 'checked_in', 'Checked In'
        NO_SHOW = 'no_show', 'No Show'
        EXCUSED = 'excused', 'Excused'

    session = models.ForeignKey(
        TryoutSession,
        on_delete=models.CASCADE,
        related_name='check_ins',
    )
    player = models.ForeignKey(
        'players.Player',
        on_delete=models.CASCADE,
        related_name='check_ins',
    )
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='check_ins_performed',
    )
    qr_code_token = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CHECKED_IN,
    )

    class Meta:
        unique_together = ['session', 'player']
        ordering = ['-checked_in_at']

    def __str__(self):
        return f'{self.player} @ {self.session.name} — {self.get_status_display()}'
