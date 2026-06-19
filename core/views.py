from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Coach, CoachSeason, UserRole
from communications.models import RSVP
from core.models import AuditLog, ImportRun
from draft.models import DraftPick, DraftSession
from evaluations.models import Evaluation
from players.models import (Division, PlayerSeason, Season, Station, Team,
                            TeamSeason)
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

        # Next upcoming sessions for the dashboard preview
        context["admin_upcoming_sessions"] = upcoming_sessions.select_related(
            "division"
        ).order_by("date", "start_time")[:4]

        # Top draft picks for the dashboard preview
        context["top_picks"] = (
            DraftPick.objects.filter(draft_session__season=active_season)
            .select_related("player_season__player", "team_season__team")
            .order_by("pick_number")[:5]
        )

        # Attention inbox items derived from live data
        attention = []
        if last_import and last_import.flagged_for_review:
            attention.append(
                {
                    "level": "danger" if last_import.flagged_for_review > 5 else "warn",
                    "title": f'{last_import.flagged_for_review} flagged SportsConnect record{"s" if last_import.flagged_for_review != 1 else ""}',
                    "sub": "Review before next import run",
                    "meta": f'{last_import.started_at.strftime("%-I:%M") if last_import else "—"}',
                    "url": "import_history",
                }
            )
        rsvp_val = context.get("rsvp_rate", 100)
        if rsvp_val < 75:
            attention.append(
                {
                    "level": "warn",
                    "title": f"RSVP rate at {rsvp_val}%",
                    "sub": "Send reminders to lift participation",
                    "meta": "—",
                    "url": None,
                }
            )
        for ds in draft_sessions:
            if ds.status == "drafting":
                attention.append(
                    {
                        "level": "info",
                        "title": f"{ds.division.name} draft in progress",
                        "sub": f"Round {ds.current_round} · pick {ds.current_pick}",
                        "meta": "now",
                        "url": "draft:index",
                    }
                )
        context["attention_items"] = attention
        counts = {"danger": 0, "warn": 0, "info": 0}
        for item in attention:
            counts[item["level"]] = counts.get(item["level"], 0) + 1
        context["attention_counts"] = counts

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
