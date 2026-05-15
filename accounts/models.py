from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TimeStampedModel


class User(AbstractUser):
    """Custom user model. Email-based auth, no Google/allauth dependency."""
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email


class UserRole(models.Model):
    """Role assignments — a user can have multiple roles across divisions."""
    ROLE_CHOICES = [
        ('cto', 'CTO / Admin'),
        ('ses_manager', 'SES Manager'),
        ('vp_player_agents', 'VP of Player Agents'),
        ('president', 'President'),
        ('player_agent', 'Player Agent'),
        ('head_coach', 'Head Coach'),
        ('assistant_coach', 'Assistant Coach'),
        ('front_desk', 'Front Desk'),
        ('comms_editor', 'Comms Editor'),
    ]
    GLOBAL_ROLES = ['cto', 'ses_manager', 'vp_player_agents', 'president']

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    league = models.ForeignKey('players.League', on_delete=models.CASCADE)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    division = models.ForeignKey(
        'players.Division', on_delete=models.CASCADE, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='roles_assigned'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'role', 'division']

    def __str__(self):
        scope = self.division.name if self.division else 'Global'
        return f"{self.user.email} — {self.get_role_display()} ({scope})"


class Coach(TimeStampedModel):
    """A coach profile linked to a user account."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='coach_profile')
    league = models.ForeignKey('players.League', on_delete=models.CASCADE, related_name='coaches')
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"Coach: {self.user.get_full_name() or self.user.email}"


class CoachSeason(TimeStampedModel):
    """A coach's assignment to a team for a specific season."""
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name='seasons')
    team_season = models.ForeignKey(
        'players.TeamSeason', on_delete=models.CASCADE, related_name='coaches'
    )
    season = models.ForeignKey(
        'players.Season', on_delete=models.CASCADE, related_name='coach_seasons'
    )
    role = models.CharField(max_length=20, choices=[
        ('head_coach', 'Head Coach'),
        ('assistant_coach', 'Assistant Coach'),
    ])
    is_drafter = models.BooleanField(default=False)

    class Meta:
        unique_together = ['coach', 'team_season']

    def __str__(self):
        return f"{self.coach} — {self.team_season} ({self.get_role_display()})"
