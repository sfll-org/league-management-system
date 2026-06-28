"""SFLL v2 URL Configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from communications import views as comms_views
from core.views import dashboard, health_check
from tryouts import views as tryouts_views

admin.site.site_header = "SFLL — League Management System"
admin.site.site_title = "SFLL Admin"
admin.site.index_title = "Operations"

urlpatterns = [
    path("", dashboard, name="home"),
    path("dashboard/", dashboard, name="dashboard"),
    path("", include("core.urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("players/", include("players.urls")),
    path("ses/", include("tryouts.urls")),
    path("evals/", include("evaluations.urls")),
    path("draft/", include("draft.urls")),
    path("comms/", include("communications.urls")),
    path("healthz", health_check, name="health-check"),
    # Public check-in via QR code (no auth required)
    path(
        "checkin/<uuid:token>/", tryouts_views.checkin_by_token, name="public_checkin"
    ),
    # Public RSVP page (no auth required)
    path("rsvp/<uuid:token>/", comms_views.public_rsvp, name="public_rsvp"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
