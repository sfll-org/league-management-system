from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Session(TimeStampedModel):
    """An SES (Skills Evaluation Session) event."""

    season = models.ForeignKey(
        "players.Season", on_delete=models.CASCADE, related_name="sessions"
    )
    name = models.CharField(max_length=200)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    division = models.ForeignKey(
        "players.Division", on_delete=models.CASCADE, related_name="sessions"
    )
    location = models.CharField(max_length=200, blank=True)
    is_makeup = models.BooleanField(default=False)
    makeup_for = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="makeup_sessions",
    )

    class Meta:
        ordering = ["-date", "start_time"]

    def __str__(self):
        return f"{self.name} — {self.date}"


class SessionAssignment(TimeStampedModel):
    """Assigns a player to an SES session."""

    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="assignments"
    )
    player_season = models.ForeignKey(
        "players.PlayerSeason",
        on_delete=models.CASCADE,
        related_name="session_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )

    class Meta:
        unique_together = ["session", "player_season"]

    def __str__(self):
        return f"{self.player_season} -> {self.session}"


class CheckIn(TimeStampedModel):
    """Records a player's check-in at an SES session."""

    session_assignment = models.OneToOneField(
        SessionAssignment, on_delete=models.CASCADE, related_name="checkin"
    )
    checked_in_at = models.DateTimeField(auto_now_add=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Check-in: {self.session_assignment} at {self.checked_in_at}"
