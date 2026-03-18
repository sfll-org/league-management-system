from django.db import models
from django.conf import settings

from core.models import TimeStampedModel


class Division(TimeStampedModel):
    """Age-based playing division (e.g., Majors, AAA, AA)."""
    name = models.CharField(max_length=50, unique=True)
    age_min = models.PositiveIntegerField()
    age_max = models.PositiveIntegerField()
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-age_max']

    def __str__(self):
        return f'{self.name} (ages {self.age_min}-{self.age_max})'


class Team(TimeStampedModel):
    """A team within a division for a given season."""
    name = models.CharField(max_length=100)
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name='teams',
    )
    head_coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coached_teams',
    )
    assistant_coaches = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='assistant_coached_teams',
    )
    season = models.CharField(max_length=20, default='Spring')
    year = models.PositiveIntegerField()

    class Meta:
        ordering = ['division', 'name']
        unique_together = ['name', 'division', 'season', 'year']

    def __str__(self):
        return f'{self.name} ({self.division.name} {self.season} {self.year})'


class Player(TimeStampedModel):
    """A registered player in the league."""

    class Gender(models.TextChoices):
        MALE = 'M', 'Male'
        FEMALE = 'F', 'Female'

    class RegistrationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        REGISTERED = 'registered', 'Registered'
        WAITLISTED = 'waitlisted', 'Waitlisted'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    # Identity
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=Gender.choices)

    # League placement
    division = models.ForeignKey(
        Division,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='players',
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='players',
    )

    # Parent / guardian
    parent_name = models.CharField(max_length=200)
    parent_email = models.EmailField()
    parent_phone = models.CharField(max_length=20)

    # Emergency & medical
    emergency_contact = models.CharField(max_length=200, blank=True, default='')
    medical_notes = models.TextField(blank=True, default='')

    # Media
    photo = models.ImageField(upload_to='players/photos/', blank=True, null=True)

    # External IDs
    sportsconnect_id = models.CharField(max_length=100, blank=True, default='')

    # Status
    registration_status = models.CharField(
        max_length=20,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.PENDING,
    )

    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['division']),
            models.Index(fields=['registration_status']),
        ]

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'
