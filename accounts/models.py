from django.db import models
from django.conf import settings

from core.models import TimeStampedModel


class UserProfile(TimeStampedModel):
    """Extended profile for league users with role-based access."""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        BOARD_MEMBER = 'board_member', 'Board Member'
        COACH = 'coach', 'Coach'
        EVALUATOR = 'evaluator', 'Evaluator'
        VOLUNTEER = 'volunteer', 'Volunteer'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VOLUNTEER,
    )
    divisions = models.ManyToManyField(
        'players.Division',
        blank=True,
        related_name='users',
    )

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.email} ({self.get_role_display()})'
