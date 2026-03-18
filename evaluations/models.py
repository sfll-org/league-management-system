from django.db import models
from django.conf import settings

from core.models import TimeStampedModel


class EvaluationCriteria(TimeStampedModel):
    """Defines what is scored at a tryout station."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    division = models.ForeignKey(
        'players.Division',
        on_delete=models.CASCADE,
        related_name='evaluation_criteria',
    )
    min_score = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)

    class Meta:
        verbose_name_plural = 'evaluation criteria'
        ordering = ['division', 'name']

    def __str__(self):
        return f'{self.name} ({self.division.name})'


class Evaluation(TimeStampedModel):
    """A single evaluation of a player at a tryout station."""
    player = models.ForeignKey(
        'players.Player',
        on_delete=models.CASCADE,
        related_name='evaluations',
    )
    session = models.ForeignKey(
        'tryouts.TryoutSession',
        on_delete=models.CASCADE,
        related_name='evaluations',
    )
    station = models.ForeignKey(
        'tryouts.Station',
        on_delete=models.CASCADE,
        related_name='evaluations',
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='evaluations_given',
    )
    scores = models.JSONField(default=dict, blank=True, help_text='Criterion name -> score mapping')
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Eval: {self.player} @ {self.station.name}'


class CoachRanking(TimeStampedModel):
    """A coach's personal ranking of players in a division."""
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coach_rankings',
    )
    player = models.ForeignKey(
        'players.Player',
        on_delete=models.CASCADE,
        related_name='coach_rankings',
    )
    division = models.ForeignKey(
        'players.Division',
        on_delete=models.CASCADE,
        related_name='coach_rankings',
    )
    rank = models.PositiveIntegerField()
    notes = models.TextField(blank=True, default='')
    season = models.CharField(max_length=20, default='Spring')
    year = models.PositiveIntegerField()

    class Meta:
        unique_together = ['coach', 'player', 'season', 'year']
        ordering = ['division', 'rank']

    def __str__(self):
        return f'#{self.rank} {self.player} by {self.coach}'
