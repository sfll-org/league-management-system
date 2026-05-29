import uuid

from django.db import models

from core.models import TimeStampedModel


class League(TimeStampedModel):
    """A Little League organization."""
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=20)
    domain = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(upload_to='leagues/logos/', blank=True, null=True)
    timezone = models.CharField(max_length=50, default='America/New_York')
    sportsconnect_report_url = models.URLField(blank=True)
    sportsconnect_sync_interval_minutes = models.PositiveIntegerField(default=60)

    def __str__(self):
        return self.short_name


class Season(TimeStampedModel):
    """A playing season within a league."""
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='seasons')
    name = models.CharField(max_length=100)
    year = models.PositiveIntegerField()
    season_type = models.CharField(max_length=10, choices=[
        ('spring', 'Spring'),
        ('fall', 'Fall'),
        ('summer', 'Summer'),
    ])
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    registration_open = models.BooleanField(default=False)
    draft_complete = models.BooleanField(default=False)

    class Meta:
        ordering = ['-year', 'season_type']

    def __str__(self):
        return f"{self.name} ({self.year})"


class Division(TimeStampedModel):
    """Age-based playing division (e.g., Majors, AAA, AA, A, Rookie)."""
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='divisions')
    name = models.CharField(max_length=50)
    display_order = models.PositiveIntegerField(default=0)
    has_leagues = models.BooleanField(
        default=False,
        help_text='If true, this division splits into sub-leagues (e.g., American/National).',
    )
    league_names = models.JSONField(
        default=list, blank=True,
        help_text='Sub-league names, e.g. ["American", "National"].',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.name


class Station(TimeStampedModel):
    """League-level evaluation station configuration (e.g., Hitting, Infield)."""
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='stations')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    eval_fields = models.JSONField(
        default=list,
        help_text='List of field definitions: [{key, label, type, min, max}, ...]',
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f"{self.name} ({self.league.short_name})"


class Player(TimeStampedModel):
    """A player known to the league (global record, not per-season)."""
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='players')
    sportsconnect_player_id = models.CharField(max_length=100, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['sportsconnect_player_id']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class PlayerSeason(TimeStampedModel):
    """A player's registration for a specific season."""
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='seasons')
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='player_seasons')
    division = models.ForeignKey(
        Division, on_delete=models.CASCADE, null=True, blank=True, related_name='player_seasons'
    )
    assigned_team = models.ForeignKey(
        'TeamSeason', on_delete=models.SET_NULL, null=True, blank=True, related_name='players'
    )
    coaches_child_of = models.ForeignKey(
        'accounts.CoachSeason', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coaches_children',
    )
    is_protected = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default='registered')
    draft_slot = models.PositiveIntegerField(null=True, blank=True)
    is_top_4 = models.BooleanField(default=False)
    jersey_number = models.PositiveSmallIntegerField(null=True, blank=True)

    # Contact / account info from SportsConnect
    account_name = models.CharField(max_length=200, blank=True)
    account_email = models.EmailField(blank=True)
    additional_email = models.EmailField(blank=True)
    order_id = models.CharField(max_length=100, blank=True)
    sportsconnect_order_detail_id = models.CharField(max_length=100, blank=True)

    # Tokens for RSVP and check-in
    rsvp_token = models.UUIDField(default=uuid.uuid4, unique=True)
    checkin_token = models.UUIDField(default=uuid.uuid4, unique=True)

    # Compliance fields — manually entered by office until SportsConnect API audit (SFLL-120)
    photo_release = models.BooleanField(null=True, blank=True)
    medical_form = models.BooleanField(null=True, blank=True)
    balance_outstanding = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ['player', 'season']
        ordering = ['player__last_name', 'player__first_name']

    def __str__(self):
        return f"{self.player} — {self.season}"


class Team(TimeStampedModel):
    """A team within a league (persistent identity across seasons)."""
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class TeamSeason(TimeStampedModel):
    """A team's participation in a specific season and division."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='seasons')
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='team_seasons')
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='team_seasons')
    sub_league = models.CharField(max_length=50, blank=True)
    drafter = models.ForeignKey(
        'accounts.CoachSeason', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='drafting_for',
    )

    class Meta:
        unique_together = ['team', 'season']

    def __str__(self):
        sub = f" ({self.sub_league})" if self.sub_league else ""
        return f"{self.team.name} — {self.division.name}{sub} ({self.season})"
