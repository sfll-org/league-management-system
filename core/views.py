from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from accounts.models import Coach, CoachSeason, UserRole
from core.models import AuditLog, ImportRun
from draft.models import DraftSession
from evaluations.models import Evaluation
from players.models import Division, PlayerSeason, Season, Station, Team, TeamSeason
from tryouts.models import CheckIn, Session, SessionAssignment
from communications.models import RSVP


def _greeting():
    """Time-of-day greeting in league-local terms. Server-local hour for now;
    SFLL-117's settings work will replace this with the league's timezone."""
    hour = timezone.localtime().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def _try_reverse(view_name, *args, **kwargs):
    """reverse() that swallows NoReverseMatch — convenient for dashboard
    cross-links to surfaces that don't have URL names yet in early phases."""
    try:
        return reverse(view_name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return None


def _build_pacific_context(active_season, player_seasons, sessions, evaluations):
    """Compute the design-aligned context dict that templates/dashboard.html
    reads (SFLL-93). Returns the keys the new template expects without
    disturbing the legacy keys callers may still reference."""
    ctx = {}

    if not active_season:
        ctx["dashboard_stats"] = [
            {
                "label": "Active season",
                "value": "—",
                "delta": "Start one to see live counts.",
                "delta_kind": "flat",
            },
        ]
        return ctx

    # — Stat row —
    total_players = player_seasons.count()
    unassigned = player_seasons.filter(assigned_team__isnull=True).count()
    unassigned_top4 = player_seasons.filter(
        assigned_team__isnull=True, is_top_4=True
    ).count()
    total_eval_target = SessionAssignment.objects.filter(
        session__season=active_season
    ).count()
    eval_pct = (
        round(evaluations.count() * 100.0 / total_eval_target)
        if total_eval_target
        else 0
    )

    # Coach certs — placeholder until a compliance model lands.
    coach_total = CoachSeason.objects.filter(season=active_season).count()
    coach_certified = coach_total  # treat all as valid until certs ship

    ctx["dashboard_stats"] = [
        {
            "label": "Registered players",
            "value": total_players,
            "delta": "Live count from PlayerSeason",
            "delta_kind": "flat",
        },
        {
            "label": "Unassigned",
            "value": unassigned,
            "delta": (
                f"{unassigned_top4} Top-4 protected"
                if unassigned_top4
                else "All protected slots placed."
            ),
            "delta_kind": "down" if unassigned_top4 else "up",
        },
        {
            "label": "Coach certs valid",
            "value": coach_certified,
            "value_suffix": f"/{coach_total}" if coach_total else "",
            "delta": "Compliance tracking lands later.",
            "delta_kind": "flat",
        },
        {
            "label": "SES completion",
            "value": f"{eval_pct}%",
            "delta": (
                f"{evaluations.count()} of {total_eval_target} evals submitted"
                if total_eval_target
                else "No assignments yet."
            ),
            "delta_kind": "up" if eval_pct >= 75 else "flat",
        },
    ]

    # — Season summary line —
    parts = []
    if active_season.start_date:
        delta = (active_season.start_date - timezone.now().date()).days
        if delta > 0:
            parts.append(f"{delta} days until Opening Day")
        elif delta == 0:
            parts.append("Opening Day is today")
        else:
            parts.append(f"In progress · {-delta} days in")
    ctx["season_summary"] = " · ".join(parts) if parts else None

    # — Divisions table —
    division_status_map = {
        ds.division_id: ds for ds in DraftSession.objects.filter(season=active_season)
    }
    division_rows = []
    for div in Division.objects.filter(
        league=active_season.league, is_active=True
    ).order_by("display_order"):
        d_players = player_seasons.filter(division=div).count()
        d_teams = TeamSeason.objects.filter(season=active_season, division=div).count()
        ds = division_status_map.get(div.id)
        if ds is None:
            status_kind, status_label = "primary", "Registering"
        elif getattr(ds, "is_complete", False) or getattr(ds, "completed_at", None):
            status_kind, status_label = "success", "Drafted"
        else:
            status_kind, status_label = "warn", "Drafting"
        division_rows.append(
            {
                "name": div.name,
                "ages": "",  # Division has no min/max age fields today; surface when added
                "players": d_players,
                "teams": d_teams,
                "status_kind": status_kind,
                "status_label": status_label,
                "url": _try_reverse("players:index") or "#",
            }
        )
    ctx["division_rows"] = division_rows

    # — Attention inbox — derive from observable state. v1 is intentionally
    # minimal; SFLL has a follow-up to wire compliance + comms-derived alerts.
    attention = []
    if unassigned_top4:
        attention.append(
            {
                "level": "danger",
                "title": f"{unassigned_top4} Top-4 player{'s' if unassigned_top4 != 1 else ''}"
                " still without a team",
                "sub": "Protected slots — draft cleanup needed.",
                "url": _try_reverse("draft:index"),
                "meta": "now",
                "is_today": True,
            }
        )
    if unassigned > unassigned_top4:
        remaining = unassigned - unassigned_top4
        attention.append(
            {
                "level": "warn",
                "title": f"{remaining} unassigned player{'s' if remaining != 1 else ''}",
                "sub": "Pending team placement.",
                "url": _try_reverse("players:index"),
                "meta": "this week",
                "is_today": False,
            }
        )
    last_import = ImportRun.objects.order_by("-started_at").first()
    if last_import and getattr(last_import, "flagged_for_review", 0):
        attention.append(
            {
                "level": "info",
                "title": f"Latest import flagged {last_import.flagged_for_review} record"
                f"{'s' if last_import.flagged_for_review != 1 else ''}",
                "sub": "Review division changes and family matches.",
                "url": _try_reverse("core:imports") or "#",
                "meta": timezone.localtime(last_import.started_at)
                .strftime("%-I%p")
                .lower(),
                "is_today": last_import.started_at.date() == timezone.now().date(),
            }
        )
    ctx["attention_items"] = attention

    # — Upcoming SES sessions —
    today = timezone.now().date()
    upcoming = (
        sessions.filter(date__gte=today).select_related("division").order_by("date")[:3]
    )
    rows = []
    for s in upcoming:
        assignments = SessionAssignment.objects.filter(session=s).count()
        checkins = CheckIn.objects.filter(session_assignment__session=s).count()
        rows.append(
            {
                "name": getattr(s, "name", None)
                or f"{s.division.name} SES — {s.date.strftime('%A')}",
                "when": s.date.strftime("%b %-d, %Y")
                + (
                    f" · {s.start_time.strftime('%-I:%M %p')}"
                    if getattr(s, "start_time", None)
                    else ""
                ),
                "location": getattr(s, "location", "") or "",
                "checked_in": checkins,
                "expected": assignments,
                "url": _try_reverse("tryouts:detail", s.id)
                or _try_reverse("tryouts:index")
                or "#",
            }
        )
    ctx["upcoming_session_rows"] = rows

    # — Top of the draft board: top 4 by Majors division —
    majors = Division.objects.filter(
        league=active_season.league, name__iexact="Majors"
    ).first()
    if majors:
        top = player_seasons.filter(division=majors, is_top_4=True).select_related(
            "player", "assigned_team__team"
        )[:6]
        top_players = []
        for ps in top:
            team_label = (
                ps.assigned_team.team.name if ps.assigned_team else "Unassigned"
            )
            top_players.append(
                {
                    "full_name": ps.player.full_name,
                    "detail": team_label,
                    "is_top_4": ps.is_top_4,
                    "team_label": team_label,
                    "url": _try_reverse("players:detail", ps.player.id) or "#",
                }
            )
        ctx["top_players"] = top_players
        ctx["top_division_name"] = majors.name
    else:
        ctx["top_players"] = []

    # — Recent imports —
    imports = ImportRun.objects.order_by("-started_at")[:3]
    import_rows = []
    for imp in imports:
        flagged = getattr(imp, "flagged_for_review", 0)
        new_players = getattr(imp, "new_players", 0)
        # Simple "Xh ago"-style relative time
        elapsed = timezone.now() - imp.started_at
        if elapsed < timedelta(minutes=60):
            rel = f"{int(elapsed.total_seconds() / 60)}m ago"
        elif elapsed < timedelta(hours=24):
            rel = f"{int(elapsed.total_seconds() / 3600)}h ago"
        else:
            rel = f"{elapsed.days}d ago"
        plural = "s" if new_players != 1 else ""
        if new_players == 0 and flagged == 0:
            level, title, sub = "info", "Auto-import · 0 changes", "Quiet hour."
        elif flagged:
            level = "info"
            title = f"Auto-import · {new_players} new player{plural}"
            sub = f"{flagged} flagged for review · {new_players - flagged} clean"
        else:
            level = "success"
            title = f"Auto-import · {new_players} new player{plural}"
            sub = "All clean."
        import_rows.append({"level": level, "title": title, "sub": sub, "when": rel})
    ctx["recent_import_rows"] = import_rows

    return ctx


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
        "greeting": _greeting(),
    }

    if not active_season:
        context.update(
            _build_pacific_context(
                None,
                PlayerSeason.objects.none(),
                Session.objects.none(),
                Evaluation.objects.none(),
            )
        )
        return render(request, "dashboard.html", context)

    # ------- Shared stats -------
    player_seasons = PlayerSeason.objects.filter(season=active_season)
    sessions = Session.objects.filter(season=active_season)
    evaluations = Evaluation.objects.filter(session__season=active_season)

    context["player_count"] = player_seasons.count()
    context["session_count"] = sessions.count()
    context["eval_count"] = evaluations.count()
    context["draft_status"] = "Complete" if active_season.draft_complete else "Pending"

    # ------- Pacific dashboard context (SFLL-93) -------
    context.update(
        _build_pacific_context(active_season, player_seasons, sessions, evaluations)
    )

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
