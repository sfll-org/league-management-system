from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base with created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Immutable audit trail for entity changes."""

    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    action = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=50)
    entity_id = models.PositiveIntegerField()
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id} at {self.timestamp}"


class ImportRun(TimeStampedModel):
    """Tracks a SportsConnect import batch."""

    league = models.ForeignKey(
        "players.League", on_delete=models.CASCADE, related_name="import_runs"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
    )
    source_url = models.URLField(blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    new_players = models.PositiveIntegerField(default=0)
    new_player_seasons = models.PositiveIntegerField(default=0)
    updated_records = models.PositiveIntegerField(default=0)
    flagged_for_review = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    error_details = models.JSONField(default=list, blank=True)
    triggered_by = models.CharField(
        max_length=20,
        choices=[
            ("scheduled", "Scheduled"),
            ("manual", "Manual"),
        ],
    )

    def __str__(self):
        return f"Import #{self.pk} ({self.status}) — {self.total_rows} rows"


class ImportFlag(TimeStampedModel):
    """A flagged record from an import run that needs human review."""

    import_run = models.ForeignKey(
        ImportRun, on_delete=models.CASCADE, related_name="flags"
    )
    flag_type = models.CharField(
        max_length=30,
        choices=[
            ("potential_duplicate", "Potential Duplicate"),
            ("division_change", "Division Change"),
            ("cancellation", "Possible Cancellation"),
            ("data_mismatch", "Data Mismatch"),
        ],
    )
    player_season = models.ForeignKey(
        "players.PlayerSeason", on_delete=models.SET_NULL, null=True, blank=True
    )
    details = models.JSONField(default=dict)
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.get_flag_type_display()} — Import #{self.import_run_id}"
