from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Evaluation(TimeStampedModel):
    """A coach's evaluation of a player at a specific station during an SES session."""
    player_season = models.ForeignKey(
        'players.PlayerSeason', on_delete=models.CASCADE, related_name='evaluations'
    )
    session = models.ForeignKey(
        'tryouts.Session', on_delete=models.CASCADE, related_name='evaluations'
    )
    coach_season = models.ForeignKey(
        'accounts.CoachSeason', on_delete=models.CASCADE, related_name='evaluations'
    )
    station = models.ForeignKey(
        'players.Station', on_delete=models.CASCADE, related_name='evaluations'
    )
    scores = models.JSONField(default=dict)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['player_season', 'session', 'coach_season', 'station']
        ordering = ['-created_at']

    def __str__(self):
        return f"Eval: {self.player_season} @ {self.station.name}"


class ObjectiveMetric(TimeStampedModel):
    """An objective measurement (e.g., sprint time, throw velocity)."""
    player_season = models.ForeignKey(
        'players.PlayerSeason', on_delete=models.CASCADE, related_name='objective_metrics'
    )
    session = models.ForeignKey(
        'tryouts.Session', on_delete=models.CASCADE, related_name='objective_metrics'
    )
    metric_type = models.CharField(max_length=50)
    value = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=20)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )

    def __str__(self):
        return f"{self.metric_type}: {self.value}{self.unit} — {self.player_season}"


class CoachRanking(TimeStampedModel):
    """A coach's personal ranking of a player (pre-draft)."""
    coach_season = models.ForeignKey(
        'accounts.CoachSeason', on_delete=models.CASCADE, related_name='rankings'
    )
    player_season = models.ForeignKey(
        'players.PlayerSeason', on_delete=models.CASCADE, related_name='ranked_by'
    )
    rank_order = models.PositiveIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['coach_season', 'player_season']
        ordering = ['rank_order']

    def __str__(self):
        return f"#{self.rank_order} {self.player_season} by {self.coach_season}"
