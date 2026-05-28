"""Coach Field Mode views (SFLL-113, Phase 8).

Mobile-first coach surface: Today / Roster / Lineup. Views are intentionally
lightweight context-builders that hand the templates flat dicts so the field
templates (which run on the phone in spotty cellular coverage) don't do any
ORM work in the render path. Models that don't exist yet (a Game model
separate from SES Session, a Compliance model) are stubbed via small helper
functions so the surface renders against real data where it exists and
graceful placeholders where it doesn't — Phase 2 set the same pattern.
"""

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from accounts.models import Coach, CoachSeason
from communications.models import RSVP
from players.models import PlayerSeason, Season
from tryouts.models import Session, SessionAssignment


# ─── Helpers ───────────────────────────────────────────────────────────────


def _initials(first_name: str, last_name: str) -> str:
    """Two-letter avatar fallback. Mirrors the dashboard's avatar pattern."""
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    if first and last:
        return (first[0] + last[0]).upper()
    if first:
        return first[:2].upper()
    if last:
        return last[:2].upper()
    return "··"


def _greeting() -> str:
    """Time-of-day greeting in league-local terms. Mirrors core/views.py;
    duplicating the helper rather than re-exporting it keeps the field
    views import-light (no circular risk on a future split)."""
    hour = timezone.localtime().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def _get_active_season():
    return Season.objects.filter(is_active=True).first()


def _get_coach_team(user, active_season):
    """Resolve the requester's CoachSeason for the active season, or None.

    A user can have multiple CoachSeason rows (e.g. drafted into two teams);
    the field surface scopes to the first head-coach assignment, then the
    first assistant-coach assignment if no head-coach row exists. League
    side decides who's the canonical drafter for the team — Phase 8
    doesn't need to."""
    if not active_season:
        return None
    try:
        coach = Coach.objects.get(user=user)
    except Coach.DoesNotExist:
        return None
    qs = (
        CoachSeason.objects.filter(coach=coach, season=active_season)
        .select_related("team_season__team", "team_season__division")
        .order_by("role")
    )
    return qs.first()


def _next_session_for_team(team_season, active_season):
    """Next upcoming Session for the team's division. Sessions are the
    closest thing the model has to a scheduled event today; once a Game
    model lands (LMS v3 roadmap) this swaps to a unified events query."""
    if not team_season or not active_season:
        return None
    today = timezone.now().date()
    return (
        Session.objects.filter(
            season=active_season,
            division=team_season.division,
            date__gte=today,
        )
        .order_by("date", "start_time")
        .first()
    )


def _week_rows(team_season, active_season, reference_date):
    """Build a 7-day strip starting at reference_date. Every day shows up;
    empty days render as "Rest day" so the coach can scan the whole week
    at a glance without scrolling past invisible gaps."""
    if not team_season or not active_season:
        return []
    week_end = reference_date + timedelta(days=6)
    sessions = (
        Session.objects.filter(
            season=active_season,
            division=team_season.division,
            date__gte=reference_date,
            date__lte=week_end,
        )
        .order_by("date", "start_time")
    )
    by_day: dict[date, list[Session]] = {}
    for s in sessions:
        by_day.setdefault(s.date, []).append(s)

    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    rows = []
    for offset in range(7):
        d = reference_date + timedelta(days=offset)
        day_sessions = by_day.get(d, [])
        if day_sessions:
            s = day_sessions[0]
            title = s.name or "Practice"
            sub_parts = []
            if s.start_time:
                sub_parts.append(s.start_time.strftime("%-I:%M %p"))
            if s.location:
                sub_parts.append(s.location)
            extras = len(day_sessions) - 1
            if extras:
                sub_parts.append(f"+{extras} more")
            rows.append(
                {
                    "day": d.strftime("%-d"),
                    "dow": dow_names[d.weekday()],
                    "title": title,
                    "sub": " · ".join(sub_parts),
                    "is_rest": False,
                }
            )
        else:
            rows.append(
                {
                    "day": d.strftime("%-d"),
                    "dow": dow_names[d.weekday()],
                    "title": "Rest day",
                    "sub": "",
                    "is_rest": True,
                }
            )
    return rows


def _rsvp_rows_for_session(session, team_season):
    """For each player on the coach's team that's assigned to the session,
    return a row with their current RSVP status. Players assigned to the
    session but not on the coach's team are excluded — the coach only
    sees their own roster."""
    if not session or not team_season:
        return [], {"attending": 0, "maybe": 0, "declined": 0, "none": 0}

    assignments = (
        SessionAssignment.objects.filter(
            session=session,
            player_season__assigned_team=team_season,
        )
        .select_related("player_season__player")
    )

    rsvp_by_player = {
        r.player_season_id: r.status
        for r in RSVP.objects.filter(
            session=session,
            player_season__assigned_team=team_season,
        )
    }

    counts = {"attending": 0, "maybe": 0, "declined": 0, "none": 0}
    rows = []
    for a in assignments:
        ps = a.player_season
        status = rsvp_by_player.get(ps.id)
        if status == "attending":
            counts["attending"] += 1
        elif status == "maybe":
            counts["maybe"] += 1
        elif status == "not_attending":
            counts["declined"] += 1
        else:
            counts["none"] += 1
        player = ps.player
        rows.append(
            {
                "id": ps.id,
                "name": player.full_name,
                "initials": _initials(player.first_name, player.last_name),
                "detail": ps.account_name or "",
                "status": status or "",
            }
        )
    rows.sort(key=lambda r: r["name"].lower())
    return rows, counts


def _compliance_ping(coach_season):
    """Surface a single high-priority compliance gap. The compliance model
    doesn't ship until a later phase (Phase 2 PR notes this as a known
    placeholder); for now the only signal we have is whether the coach
    has filled in a phone number — useful as a stand-in until the real
    background-check / training tracker exists."""
    if not coach_season:
        return None
    coach = coach_season.coach
    if not coach.phone:
        return {
            "title": "Add a phone number",
            "sub": "Parents need a way to reach you on the field.",
            "url": reverse("dashboard"),  # account page lands in a later phase
        }
    return None


def _team_label(coach_season):
    if not coach_season:
        return None
    ts = coach_season.team_season
    label = ts.team.name
    if ts.sub_league:
        label += f" · {ts.sub_league}"
    return f"{label} · {ts.division.name}"


def _roster_rows(team_season):
    if not team_season:
        return []
    qs = PlayerSeason.objects.filter(assigned_team=team_season).select_related("player")
    today = timezone.now().date()
    rows = []
    for ps in qs:
        p = ps.player
        age = None
        if p.date_of_birth:
            years = today.year - p.date_of_birth.year
            if (today.month, today.day) < (p.date_of_birth.month, p.date_of_birth.day):
                years -= 1
            age = years
        rows.append(
            {
                "id": ps.id,
                "name": p.full_name,
                "initials": _initials(p.first_name, p.last_name),
                "account_name": ps.account_name,
                "email": ps.account_email or ps.additional_email,
                # phone isn't on the model yet — surfaced when it lands
                "tel": "",
                "age": age,
            }
        )
    return rows


def _lineup_rows(team_season):
    """For Phase 8 the lineup is just the roster pre-sorted alphabetically;
    persistence + position assignment lands in the follow-up. The position
    column renders an em-dash so the coach can see the column exists."""
    if not team_season:
        return []
    rows = _roster_rows(team_season)
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "position": "",  # filled in by a follow-up phase
        }
        for r in rows
    ]


# ─── Views ─────────────────────────────────────────────────────────────────


@login_required
def field_index(request):
    """Bare /field/ — redirect to Today so the URL is shareable."""
    return HttpResponseRedirect(reverse("field_today"))


@login_required
def field_today(request):
    active_season = _get_active_season()
    coach_season = _get_coach_team(request.user, active_season)
    team_season = coach_season.team_season if coach_season else None

    next_session = _next_session_for_team(team_season, active_season)
    rsvp_rows, rsvp_counts = _rsvp_rows_for_session(next_session, team_season)

    next_event = None
    if next_session:
        when_parts = [next_session.date.strftime("%a %b %-d")]
        if next_session.start_time:
            when_parts.append(next_session.start_time.strftime("%-I:%M %p"))
        responded = rsvp_counts["attending"] + rsvp_counts["maybe"] + rsvp_counts["declined"]
        total = responded + rsvp_counts["none"]
        next_event = {
            "kind": "Next up",
            "title": next_session.name or f"{next_session.division.name} session",
            "when": " · ".join(when_parts),
            "location": next_session.location,
            "rsvp_summary": (
                f"{rsvp_counts['attending']} of {total} confirmed"
                if total
                else None
            ),
            "directions_url": None,
        }

    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)

    context = {
        "field_active": "today",
        "greeting": _greeting(),
        "today_label": today.strftime("%A · %b %-d"),
        "team_label": _team_label(coach_season),
        "compliance_ping": _compliance_ping(coach_season),
        "next_event": next_event,
        "rsvp_rows": rsvp_rows,
        "rsvp_counts": rsvp_counts,
        "rsvp_total": sum(rsvp_counts.values()),
        "week_rows": _week_rows(team_season, active_season, week_start),
        "week_label": f"{week_start.strftime('%b %-d')} – {week_end.strftime('%b %-d')}",
    }
    return render(request, "field/today.html", context)


@login_required
def field_roster(request):
    active_season = _get_active_season()
    coach_season = _get_coach_team(request.user, active_season)
    team_season = coach_season.team_season if coach_season else None

    rows = _roster_rows(team_season)
    division_label = team_season.division.name if team_season else None

    context = {
        "field_active": "roster",
        "team_label": _team_label(coach_season),
        "division_label": division_label,
        "roster_rows": rows,
        "roster_count": len(rows),
    }
    return render(request, "field/roster.html", context)


@login_required
def field_lineup(request):
    active_season = _get_active_season()
    coach_season = _get_coach_team(request.user, active_season)
    team_season = coach_season.team_season if coach_season else None
    next_session = _next_session_for_team(team_season, active_season)

    next_event = None
    if next_session:
        next_event = {
            "title": next_session.name or f"{next_session.division.name} session",
        }

    rows = _lineup_rows(team_season)
    context = {
        "field_active": "lineup",
        "team_label": _team_label(coach_season),
        "next_event": next_event,
        "lineup_rows": rows,
        "lineup_count": len(rows),
    }
    return render(request, "field/lineup.html", context)
