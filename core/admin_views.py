"""
Admin views for Phase 6: User Management, Configuration, and Audit Log.

All views require the CTO role (or superuser).
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User, UserRole
from core.models import AuditLog
from players.models import Division, League, Station, Team, TeamSeason

# ------------------------------------------------------------------
# CTO-only access decorator (same pattern as import_views)
# ------------------------------------------------------------------


def _require_cto(user):
    """Return True if user has the CTO role or is a superuser."""
    if user.is_superuser:
        return True
    return UserRole.objects.filter(user=user, role="cto", is_active=True).exists()


def cto_required(view_func):
    """Decorator: login required + CTO role check."""

    @login_required
    def wrapper(request, *args, **kwargs):
        if not _require_cto(request.user):
            messages.error(request, "You do not have permission to access this page.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)

    wrapper.__name__ = view_func.__name__
    wrapper.__doc__ = view_func.__doc__
    return wrapper


# ==================================================================
# SFLL-82: User Management + Role Assignment
# ==================================================================


@cto_required
def user_list(request):
    """List all users with search functionality."""
    q = request.GET.get("q", "").strip()
    users = User.objects.all().prefetch_related("roles", "roles__division")

    if q:
        users = users.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
        )

    users = users.order_by("last_name", "first_name")
    paginator = Paginator(users, 25)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(
        request,
        "accounts/user_list.html",
        {
            "page_obj": page,
            "search_query": q,
        },
    )


@cto_required
def user_detail(request, pk):
    """View user details and their roles."""
    target_user = get_object_or_404(User, pk=pk)
    roles = UserRole.objects.filter(user=target_user).select_related(
        "division", "league"
    )
    return render(
        request,
        "accounts/user_detail.html",
        {
            "target_user": target_user,
            "roles": roles,
        },
    )


@cto_required
def manage_roles(request, pk):
    """Manage roles for a specific user."""
    target_user = get_object_or_404(User, pk=pk)
    roles = UserRole.objects.filter(user=target_user).select_related(
        "division", "league"
    )
    leagues = League.objects.all()
    divisions = Division.objects.filter(is_active=True).order_by("display_order")

    return render(
        request,
        "accounts/manage_roles.html",
        {
            "target_user": target_user,
            "roles": roles,
            "leagues": leagues,
            "divisions": divisions,
            "role_choices": UserRole.ROLE_CHOICES,
            "global_roles": UserRole.GLOBAL_ROLES,
        },
    )


@cto_required
def add_role(request, pk):
    """Add a role to a user."""
    if request.method != "POST":
        return redirect("manage_roles", pk=pk)

    target_user = get_object_or_404(User, pk=pk)
    role = request.POST.get("role", "")
    league_id = request.POST.get("league", "")
    division_id = request.POST.get("division", "") or None

    if not role or not league_id:
        messages.error(request, "Role and league are required.")
        return redirect("manage_roles", pk=pk)

    league = get_object_or_404(League, pk=league_id)
    division = None
    if division_id and role not in UserRole.GLOBAL_ROLES:
        division = get_object_or_404(Division, pk=division_id)

    # Check for duplicate
    existing = UserRole.objects.filter(
        user=target_user, role=role, division=division
    ).exists()
    if existing:
        messages.warning(request, "This role assignment already exists.")
        return redirect("manage_roles", pk=pk)

    UserRole.objects.create(
        user=target_user,
        league=league,
        role=role,
        division=division,
        assigned_by=request.user,
    )

    # Audit log
    AuditLog.objects.create(
        user=request.user,
        action="role_added",
        entity_type="UserRole",
        entity_id=target_user.pk,
        details={
            "role": role,
            "target_user": target_user.email,
            "division": division.name if division else None,
        },
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    messages.success(
        request, f"Added {dict(UserRole.ROLE_CHOICES).get(role, role)} role."
    )
    return redirect("manage_roles", pk=pk)


@cto_required
def remove_role(request, pk, role_id):
    """Remove a role from a user."""
    if request.method != "POST":
        return redirect("manage_roles", pk=pk)

    target_user = get_object_or_404(User, pk=pk)
    role_obj = get_object_or_404(UserRole, pk=role_id, user=target_user)

    role_display = role_obj.get_role_display()

    # Audit log
    AuditLog.objects.create(
        user=request.user,
        action="role_removed",
        entity_type="UserRole",
        entity_id=target_user.pk,
        details={
            "role": role_obj.role,
            "target_user": target_user.email,
            "division": role_obj.division.name if role_obj.division else None,
        },
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    role_obj.delete()
    messages.success(request, f"Removed {role_display} role.")
    return redirect("manage_roles", pk=pk)


# ==================================================================
# SFLL-83: Division / Team / Station Configuration
# ==================================================================


@cto_required
def config_home(request):
    """Configuration hub page — links to divisions, teams, stations."""
    division_count = Division.objects.filter(is_active=True).count()
    team_count = Team.objects.count()
    station_count = Station.objects.filter(is_active=True).count()

    return render(
        request,
        "core/config/home.html",
        {
            "division_count": division_count,
            "team_count": team_count,
            "station_count": station_count,
        },
    )


@cto_required
def division_list(request):
    """List all divisions."""
    divisions = Division.objects.all().order_by("display_order")
    return render(
        request,
        "core/config/division_list.html",
        {
            "divisions": divisions,
        },
    )


@cto_required
def division_edit(request, pk):
    """Edit a division."""
    division = get_object_or_404(Division, pk=pk)

    if request.method == "POST":
        division.name = request.POST.get("name", division.name)
        division.display_order = int(
            request.POST.get("display_order", division.display_order)
        )
        division.has_leagues = request.POST.get("has_leagues") == "on"

        league_names_raw = request.POST.get("league_names", "[]")
        try:
            division.league_names = json.loads(league_names_raw)
        except (json.JSONDecodeError, TypeError):
            # Try comma-separated fallback
            division.league_names = [
                n.strip() for n in league_names_raw.split(",") if n.strip()
            ]

        division.is_active = request.POST.get("is_active") == "on"
        division.save()

        AuditLog.objects.create(
            user=request.user,
            action="division_updated",
            entity_type="Division",
            entity_id=division.pk,
            details={"name": division.name},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        messages.success(request, f'Division "{division.name}" updated.')
        return redirect("division_list")

    return render(
        request,
        "core/config/division_edit.html",
        {
            "division": division,
        },
    )


@cto_required
def team_list(request):
    """List all teams grouped by division."""
    active_season = None
    from players.models import Season

    active_season = Season.objects.filter(is_active=True).first()

    teams_by_division = {}
    if active_season:
        team_seasons = (
            TeamSeason.objects.filter(season=active_season)
            .select_related("team", "division")
            .order_by("division__display_order", "team__name")
        )
        for ts in team_seasons:
            div_name = ts.division.name
            if div_name not in teams_by_division:
                teams_by_division[div_name] = []
            teams_by_division[div_name].append(ts)
    else:
        # No active season: just list teams
        for team in Team.objects.all().order_by("name"):
            teams_by_division.setdefault("All Teams", []).append(team)

    return render(
        request,
        "core/config/team_list.html",
        {
            "teams_by_division": teams_by_division,
            "active_season": active_season,
        },
    )


@cto_required
def station_list(request):
    """List all evaluation stations."""
    stations = Station.objects.all().order_by("display_order")
    return render(
        request,
        "core/config/station_list.html",
        {
            "stations": stations,
        },
    )


@cto_required
def station_edit(request, pk):
    """Edit a station, including its eval_fields JSON."""
    station = get_object_or_404(Station, pk=pk)

    if request.method == "POST":
        station.name = request.POST.get("name", station.name)
        station.description = request.POST.get("description", station.description)
        station.display_order = int(
            request.POST.get("display_order", station.display_order)
        )
        station.is_active = request.POST.get("is_active") == "on"

        eval_fields_raw = request.POST.get("eval_fields", "[]")
        try:
            parsed = json.loads(eval_fields_raw)
            if isinstance(parsed, list):
                station.eval_fields = parsed
            else:
                messages.error(request, "eval_fields must be a JSON array.")
                return render(
                    request, "core/config/station_edit.html", {"station": station}
                )
        except (json.JSONDecodeError, TypeError):
            messages.error(request, "Invalid JSON in eval_fields.")
            return render(
                request, "core/config/station_edit.html", {"station": station}
            )

        station.save()

        AuditLog.objects.create(
            user=request.user,
            action="station_updated",
            entity_type="Station",
            entity_id=station.pk,
            details={"name": station.name},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        messages.success(request, f'Station "{station.name}" updated.')
        return redirect("station_list")

    return render(
        request,
        "core/config/station_edit.html",
        {
            "station": station,
            "eval_fields_json": json.dumps(station.eval_fields, indent=2),
        },
    )


# ==================================================================
# SFLL-84: Audit Log Viewer
# ==================================================================


@cto_required
def audit_log(request):
    """Searchable, filterable, paginated audit log."""
    entries = AuditLog.objects.select_related("user").all()

    # Filters
    action_filter = request.GET.get("action", "").strip()
    entity_filter = request.GET.get("entity_type", "").strip()
    user_filter = request.GET.get("user_id", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    search = request.GET.get("q", "").strip()

    if action_filter:
        entries = entries.filter(action__icontains=action_filter)
    if entity_filter:
        entries = entries.filter(entity_type__icontains=entity_filter)
    if user_filter:
        entries = entries.filter(user_id=user_filter)
    if date_from:
        entries = entries.filter(timestamp__date__gte=date_from)
    if date_to:
        entries = entries.filter(timestamp__date__lte=date_to)
    if search:
        entries = entries.filter(
            Q(action__icontains=search)
            | Q(entity_type__icontains=search)
            | Q(details__icontains=search)
        )

    # Get distinct values for filter dropdowns
    action_choices = (
        AuditLog.objects.values_list("action", flat=True).distinct().order_by("action")
    )
    entity_choices = (
        AuditLog.objects.values_list("entity_type", flat=True)
        .distinct()
        .order_by("entity_type")
    )
    user_choices = User.objects.filter(
        pk__in=AuditLog.objects.values_list("user_id", flat=True).distinct()
    ).order_by("last_name", "first_name")

    paginator = Paginator(entries, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(
        request,
        "core/audit_log.html",
        {
            "page_obj": page,
            "action_filter": action_filter,
            "entity_filter": entity_filter,
            "user_filter": user_filter,
            "date_from": date_from,
            "date_to": date_to,
            "search": search,
            "action_choices": action_choices,
            "entity_choices": entity_choices,
            "user_choices": user_choices,
        },
    )
