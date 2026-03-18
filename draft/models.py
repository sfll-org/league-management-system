from django.db import models
from django.conf import settings

from core.models import TimeStampedModel


class DraftConfiguration(TimeStampedModel):
    """Configuration for a division's draft."""

    class Status(models.TextChoices):
        SETUP = 'setup', 'Setup'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'

    division = models.ForeignKey(
        'players.Division',
        on_delete=models.CASCADE,
        related_name='draft_configs',
    )
    season = models.CharField(max_length=20, default='Spring')
    year = models.PositiveIntegerField()
    num_rounds = models.PositiveIntegerField(default=10)
    snake_order = models.BooleanField(
        default=True,
        help_text='If true, pick order reverses each round.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SETUP,
    )

    class Meta:
        unique_together = ['division', 'season', 'year']
        ordering = ['-year', 'division']

    def __str__(self):
        return f'{self.division.name} Draft — {self.season} {self.year}'


class DraftPick(TimeStampedModel):
    """A single pick in a draft."""
    config = models.ForeignKey(
        DraftConfiguration,
        on_delete=models.CASCADE,
        related_name='picks',
    )
    round = models.PositiveIntegerField()
    pick_number = models.PositiveIntegerField()
    team = models.ForeignKey(
        'players.Team',
        on_delete=models.CASCADE,
        related_name='draft_picks',
    )
    player = models.ForeignKey(
        'players.Player',
        on_delete=models.CASCADE,
        related_name='draft_picks',
    )
    picked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='draft_picks_made',
    )
    picked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['config', 'pick_number']
        ordering = ['config', 'pick_number']

    def __str__(self):
        return f'Round {self.round}, Pick {self.pick_number}: {self.player} -> {self.team}'


class PlayerAgent(TimeStampedModel):
    """Tracks which players are available in a draft and any seeding."""
    player = models.ForeignKey(
        'players.Player',
        on_delete=models.CASCADE,
        related_name='draft_agents',
    )
    config = models.ForeignKey(
        DraftConfiguration,
        on_delete=models.CASCADE,
        related_name='player_agents',
    )
    is_seeded = models.BooleanField(
        default=False,
        help_text='Pre-assigned to a team (e.g., coach\'s child).',
    )
    seeded_to_team = models.ForeignKey(
        'players.Team',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seeded_players',
    )

    class Meta:
        unique_together = ['player', 'config']

    def __str__(self):
        seed = f' (seeded: {self.seeded_to_team})' if self.is_seeded else ''
        return f'{self.player}{seed}'
