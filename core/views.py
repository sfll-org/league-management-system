from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.models import Coach, CoachSeason, UserRole
from communications.models import RSVP
from core.models import AuditLog, ImportRun
from draft.models import DraftSession
from evaluations.models import Evaluation
from players.models import PlayerSeason, Season
from tryouts.models import CheckIn, Session, SessionAssignment


def _get_user_roles(user):
    """Return a set of role strings for the user."""
    if user.is_superuser:
        return {"cto"}
    return set(
        UserRole.objects.filter(user=user, is_active=True).values_list(
            "role", flat=True
        )
    )


def _is_admin(roles):
    """Return True if user has an admin-level role."""
    return bool(roles & {"cto", "ses_manager", "vp_player_agents", "president"})


def _is_coach(roles):
    """Return True if user has a coach role."""
    return bool(roles & {"head_coach", "assistant_coach"})


def _is_front_desk(roles):
    """Return True if user has the front desk role."""
    return "front_desk" in roles


@login_required
def dashboard(request):
    """Main dashboard with role-appropriate widgets."""
    active_season = Season.objects.filter(is_active=True).first()
    roles = _get_user_roles(request.user)

    context = {
        "season": active_season,
        "roles": roles,
        "is_admin": _is_admin(roles),
        "is_coach": _is_coach(roles),
        "is_front_desk": _is_front_desk(roles),
        "player_count": 0,
        "session_count": 0,
        "eval_count": 0,
        "draft_status": "No active season",
    }

    if not active_season:
        return render(request, "dashboard.html", context)

    # ------- Shared stats -------
    player_seasons = PlayerSeason.objects.filter(season=active_season)
    sessions = Session.objects.filter(season=active_season)
    evaluations = Evaluation.objects.filter(session__season=active_season)

    context["player_count"] = player_seasons.count()
    context["session_count"] = sessions.count()
    context["eval_count"] = evaluations.count()
    context["draft_status"] = "Complete" if active_season.draft_complete else "Pending"

    # ------- Admin widgets -------
    if _is_admin(roles):
        # Player counts by division
        division_counts = (
            player_seasons.values("division__name")
            .annotate(count=Count("id"))
            .order_by("division__display_order")
        )
        context["division_counts"] = division_counts

        # Registration status
        context["registration_open"] = active_season.registration_open

        # SES session stats
        today = timezone.now().date()
        upcoming_sessions = sessions.filter(date__gte=today)
        context["upcoming_session_count"] = upcoming_sessions.count()

        # RSVP rates
        total_assignments = SessionAssignment.objects.filter(
            session__season=active_season
        ).count()
        total_rsvps = RSVP.objects.filter(session__season=active_season).count()
        context["rsvp_rate"] = round(
            (total_rsvps / total_assignments * 100) if total_assignments > 0 else 0
        )

        # Check-in rates
        total_checkins = CheckIn.objects.filter(
            session_assignment__session__season=active_season
        ).count()
        context["checkin_rate"] = round(
            (total_checkins / total_assignments * 100) if total_assignments > 0 else 0
        )

        # Evaluation completion
        coaches_evaluated = evaluations.values("coach_season").distinct().count()
        players_evaluated = evaluations.values("player_season").distinct().count()
        context["coaches_evaluated"] = coaches_evaluated
        context["players_evaluated"] = players_evaluated

        # Draft status per division
        draft_sessions = DraftSession.objects.filter(
            season=active_season
        ).select_related("division")
        context["draft_sessions"] = draft_sessions

        # SportsConnect: last sync time + flagged records
        last_import = ImportRun.objects.order_by("-started_at").first()
        context["last_import"] = last_import
        if last_import:
            context["flagged_count"] = last_import.flagged_for_review

        # Recent audit log entries
        context["recent_audit"] = AuditLog.objects.select_related("user")[:10]

    # ------- Coach widgets -------
    if _is_coach(roles):
        try:
            coach = Coach.objects.get(user=request.user)
            coach_season = (
                CoachSeason.objects.filter(coach=coach, season=active_season)
                .select_related(
                    "team_season", "team_season__team", "team_season__division"
                )
                .first()
            )
            context["coach_season"] = coach_season

            if coach_season:
                # Team info
                context["team_players"] = PlayerSeason.objects.filter(
                    assigned_team=coach_season.team_season
                ).select_related("player")

                # Upcoming sessions for their division
                today = timezone.now().date()
                context["coach_upcoming_sessions"] = Session.objects.filter(
                    season=active_season,
                    division=coach_season.team_season.division,
                    date__gte=today,
                )[:5]

                # Evaluation progress
                context["coach_eval_count"] = Evaluation.objects.filter(
                    coach_season=coach_season,
                    session__season=active_season,
                ).count()

                total_players_in_division = PlayerSeason.objects.filter(
                    season=active_season,
                    division=coach_season.team_season.division,
                ).count()
                context["division_player_count"] = total_players_in_division

        except Coach.DoesNotExist:
            context["coach_season"] = None

    # ------- Front Desk widgets -------
    if _is_front_desk(roles):
        today = timezone.now().date()
        context["todays_sessions"] = sessions.filter(date=today).select_related(
            "division"
        )

    return render(request, "dashboard.html", context)


def health_check(request):
    """Health check endpoint for Docker / load balancers."""
    return JsonResponse({"status": "ok"})


# Static nav pages the ⌘K palette can jump to.
_CMDK_PAGES = [
    {"label": "Dashboard", "url": "/dashboard/", "kind": "page", "icon": "home"},
    {"label": "Players", "url": "/players/", "kind": "page", "icon": "users"},
    {"label": "Teams", "url": "/players/teams/", "kind": "page", "icon": "shield"},
    {"label": "SES Sessions", "url": "/ses/", "kind": "page", "icon": "calendar"},
    {"label": "Evaluations", "url": "/evals/", "kind": "page", "icon": "clipboard"},
    {"label": "Draft", "url": "/draft/", "kind": "page", "icon": "star"},
    {"label": "Communications", "url": "/comms/", "kind": "page", "icon": "mail"},
]


@login_required
def cmdk_search(request):
    """JSON endpoint for the ⌘K command palette.

    Only available to users with lms_power_user set. Returns pages, players,
    and families that fuzzy-match the query string.
    """
    user = request.user
    if not (user.is_superuser or user.lms_power_user):
        return JsonResponse({"error": "forbidden"}, status=403)

    q = request.GET.get("q", "").strip()
    results = []

    if not q:
        # Empty query: return all nav pages as suggestions.
        results = list(_CMDK_PAGES)
        return JsonResponse({"results": results})

    q_lower = q.lower()

    # Pages — simple substring match on label.
    for page in _CMDK_PAGES:
        if q_lower in page["label"].lower():
            results.append(page)

    # Players — match first_name, last_name, or full name.
    from players.models import Player

    players = Player.objects.filter(
        Q(first_name__icontains=q) | Q(last_name__icontains=q)
    ).order_by("last_name", "first_name")[:12]
    for p in players:
        results.append(
            {
                "label": p.full_name,
                "url": f"/players/?q={p.first_name}+{p.last_name}",
                "kind": "player",
                "icon": "user",
                "meta": "",
            }
        )

    # Families — distinct account_name from PlayerSeason.
    from players.models import PlayerSeason

    active_season = Season.objects.filter(is_active=True).first()
    family_qs = (
        PlayerSeason.objects.filter(account_name__icontains=q)
        .values_list("account_name", flat=True)
        .distinct()
        .order_by("account_name")[:8]
    )
    if active_season:
        family_qs = (
            PlayerSeason.objects.filter(season=active_season, account_name__icontains=q)
            .values_list("account_name", flat=True)
            .distinct()
            .order_by("account_name")[:8]
        )
    for name in family_qs:
        if name:
            results.append(
                {
                    "label": name,
                    "url": f"/players/?q={name}",
                    "kind": "family",
                    "icon": "users",
                    "meta": "Family",
                }
            )

    return JsonResponse({"results": results[:20]})
