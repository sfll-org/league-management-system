from django.db import models
from django.conf import settings


class TimeStampedModel(models.Model):
    """Abstract base model with created_at and updated_at timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Tracks changes across the system for accountability."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['model_name', 'object_id']),
        ]

    def __str__(self):
        return f'{self.action} {self.model_name}#{self.object_id} by {self.user}'
