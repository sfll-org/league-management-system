"""Celery configuration for SFLL project."""

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sfll.settings')

app = Celery('sfll')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Example task for testing Celery."""
    print(f'Request: {self.request!r}')
