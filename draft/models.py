from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class DraftSession(TimeStampedModel):
    """A draft event for a division (or sub-league within a division)."""

    season = models.ForeignKey(
        "players.Season", on_delete=models.CASCADE, related_name="draft_sessions"
    )
    division = models.ForeignKey(
        "players.Division", on_delete=models.CASCADE, related_name="draft_sessions"
    )
    sub_league = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("seeding", "Seeding"),
            ("drafting", "Drafting"),
            ("completed", "Completed"),
        ],
        default="pending",
    )
    current_round = models.PositiveIntegerField(default=1)
    current_pick = models.PositiveIntegerField(default=1)
    snake_draft = models.BooleanField(
        default=True,
        help_text="If true, pick order reverses each round (snake draft).",
    )
    team_order = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered list of TeamSeason PKs defining pick order.",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        sub = f" ({self.sub_league})" if self.sub_league else ""
        return f"{self.division.name}{sub} Draft — {self.season}"


class DraftPick(TimeStampedModel):
    """A single pick in a draft session."""

    draft_session = models.ForeignKey(
        DraftSession, on_delete=models.CASCADE, related_name="picks"
    )
    team_season = models.ForeignKey(
        "players.TeamSeason", on_delete=models.CASCADE, related_name="draft_picks"
    )
    player_season = models.ForeignKey(
        "players.PlayerSeason", on_delete=models.CASCADE, related_name="draft_pick"
    )
    round_number = models.PositiveIntegerField()
    pick_number = models.PositiveIntegerField()
    is_top_4 = models.BooleanField(default=False)
    is_coaches_child = models.BooleanField(default=False)
    picked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    picked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["draft_session", "pick_number"]
        ordering = ["pick_number"]

    def __str__(self):
        return f"R{self.round_number} P{self.pick_number}: {self.player_season} -> {self.team_season}"
