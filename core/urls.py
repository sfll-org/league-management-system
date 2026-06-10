"""URL configuration for the core app (imports, admin views)."""

from django.urls import path

from core import admin_views, import_views

urlpatterns = [
    # Imports (existing)
    path("admin/imports/", import_views.import_history, name="import_history"),
    path("admin/imports/upload/", import_views.import_upload, name="import_upload"),
    path(
        "admin/imports/<int:run_id>/review/",
        import_views.import_review,
        name="import_review",
    ),
    path(
        "admin/imports/<int:run_id>/resolve/<int:flag_id>/",
        import_views.resolve_flag,
        name="resolve_flag",
    ),
    path("admin/imports/trigger/", import_views.import_trigger, name="import_trigger"),
    # User Management (SFLL-82)
    path("admin/users/", admin_views.user_list, name="user_list"),
    path("admin/users/<int:pk>/", admin_views.user_detail, name="user_detail"),
    path("admin/users/<int:pk>/roles/", admin_views.manage_roles, name="manage_roles"),
    path("admin/users/<int:pk>/roles/add/", admin_views.add_role, name="add_role"),
    path(
        "admin/users/<int:pk>/roles/<int:role_id>/remove/",
        admin_views.remove_role,
        name="remove_role",
    ),
    # Configuration (SFLL-83)
    path("admin/config/", admin_views.config_home, name="config_home"),
    path("admin/config/divisions/", admin_views.division_list, name="division_list"),
    path(
        "admin/config/divisions/<int:pk>/edit/",
        admin_views.division_edit,
        name="division_edit",
    ),
    path("admin/config/teams/", admin_views.team_list, name="team_list"),
    path("admin/config/stations/", admin_views.station_list, name="station_list"),
    path(
        "admin/config/stations/<int:pk>/edit/",
        admin_views.station_edit,
        name="station_edit",
    ),
    # Audit Log (SFLL-84)
    path("admin/audit/", admin_views.audit_log, name="audit_log"),
]
