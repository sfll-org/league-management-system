"""SFLL URL Configuration."""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.views import dashboard, health_check

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('healthz', health_check, name='health-check'),
    path('players/', include('players.urls')),
    path('tryouts/', include('tryouts.urls')),
    path('evaluations/', include('evaluations.urls')),
    path('draft/', include('draft.urls')),
    path('communications/', include('communications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
