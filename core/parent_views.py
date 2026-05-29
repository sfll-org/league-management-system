"""Parent phone view (SFLL-98, Phase 7 — parent half).

Mirrors the chrome of Coach Field Mode (SFLL-113) but serves the family-side
audience: Today / Schedule / Account / Inbox. Views are light context
builders that hand the templates flat dicts, same as field_views.py.

Parent identity in this data model is denormalized — there's no Parent FK on
PlayerSeason yet, just ``account_email`` / ``additional_email`` strings. The
view resolves children by matching ``request.user.email`` against either
column. A signed-in user with no matching PlayerSeason rows still gets the
surface; the templates show empty states rather than 500ing, matching the
graceful-fallback pattern Coach Field Mode established.

Models that don't exist yet (balance, volunteer obligations, documents on
file, a unified Game model separate from SES Session) are stubbed as
None/empty so the surface renders honestly today and slots real data in
once those phases ship.
"""

from datetime import time as dt_time, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from communications.models import RSVP, EmailLog
from players.models import PlayerSeason, Season
from tryouts.models import Session, SessionAssignment


# ─── Helpers ───────────────────────────────────────────────────────────────


def _initials(first_name: str, last_name: str) -> str:
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
    hour = timezone.localtime().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def _get_active_season():
    return Season.objects.filter(is_active=True).first()


def _children_for_user(user, active_season):
    """Return PlayerSeason rows whose account_email/additional_email matches
    the signed-in user's email. Case-insensitive — parents register on
    SportsConnect with whatever capitalization they typed.

    Scoped to the active season; the parent surface always frames the
    current season's view (a parent of a graduated player should see an
    empty state, not last year's schedule)."""
    if not user.email or not active_season:
        return PlayerSeason.objects.none()
    email = user.email.strip().lower()
    return (
        PlayerSeason.objects
        .filter(season=active_season)
        .filter(
            Q(account_email__iexact=email)
            | Q(additional_email__iexact=email)
        )
        .select_related(
            "player",
            "assigned_team__team",
            "assigned_team__division",
            "division",
        )
        .order_by("player__first_name", "player__last_name")
    )


def _player_cards(children):
    """One card per child for the Today + Account screens."""
    cards = []
    today = timezone.now().date()
    for ps in children:
        p = ps.player
        age = None
        if p.date_of_birth:
            years = today.year - p.date_of_birth.year
            if (today.month, today.day) < (p.date_of_birth.month, p.date_of_birth.day):
                years -= 1
            age = years
        team_label = None
        if ps.assigned_team:
            ts = ps.assigned_team
            parts = [ts.team.name]
            if ts.sub_league:
                parts.append(ts.sub_league)
            parts.append(ts.division.name)
            team_label = " · ".join(parts)
        elif ps.division:
            team_label = f"{ps.division.name} · Unassigned"
        cards.append(
            {
                "id": ps.id,
                "name": p.full_name,
                "initials": _initials(p.first_name, p.last_name),
                "age": age,
                "team_label": team_label,
                "status": ps.status,
            }
        )
    return cards


def _next_session_for_child(player_season):
    """The next Session the player is assigned to. Falls back to the next
    Session in the player's division if no per-player assignment exists
    yet (early-season state before SES assignment runs)."""
    if not player_season:
        return None
    today = timezone.now().date()
    by_assignment = (
        Session.objects
        .filter(
            assignments__player_season=player_season,
            date__gte=today,
        )
        .order_by("date", "start_time")
        .first()
    )
    if by_assignment:
        return by_assignment
    division = player_season.assigned_team.division if player_season.assigned_team else player_season.division
    if not division:
        return None
    return (
        Session.objects
        .filter(
            season=player_season.season,
            division=division,
            date__gte=today,
        )
        .order_by("date", "start_time")
        .first()
    )


def _next_event_for_child(player_season):
    """Build the Today-screen hero block + RSVP buttons for one child."""
    session = _next_session_for_child(player_season)
    if not session:
        return None
    when_parts = [session.date.strftime("%a %b %-d")]
    if session.start_time:
        when_parts.append(session.start_time.strftime("%-I:%M %p"))
    rsvp = RSVP.objects.filter(player_season=player_season, session=session).first()
    return {
        "session_id": session.id,
        "title": session.name or f"{player_season.player.first_name}'s next session",
        "when": " · ".join(when_parts),
        "location": session.location or "",
        "status": rsvp.status if rsvp else "",
        "player_season_id": player_season.id,
    }


def _upcoming_schedule(children, days=21):
    """Flatten upcoming Sessions for any of the parent's children into a
    single date-sorted list. Three weeks ahead by default — far enough
    for a parent to plan vacations against, close enough to fit on the
    Schedule tab without scrolling forever."""
    if not children:
        return []
    today = timezone.now().date()
    horizon = today + timedelta(days=days)

    # Per-child assigned sessions
    rows_by_session = {}
    for ps in children:
        sessions = (
            Session.objects
            .filter(
                assignments__player_season=ps,
                date__gte=today,
                date__lte=horizon,
            )
            .select_related("division")
            .distinct()
        )
        rsvp_map = {
            r.session_id: r.status
            for r in RSVP.objects.filter(player_season=ps, session__in=sessions)
        }
        for s in sessions:
            row = rows_by_session.setdefault(
                (s.id, ps.id),
                {
                    "session_id": s.id,
                    "player_season_id": ps.id,
                    "player_name": ps.player.first_name,
                    "title": s.name or f"{s.division.name} session",
                    "date_label": s.date.strftime("%a %b %-d"),
                    "date_iso": s.date.isoformat(),
                    "time_label": s.start_time.strftime("%-I:%M %p") if s.start_time else "",
                    "location": s.location or "",
                    "status": rsvp_map.get(s.id, ""),
                    "sort_key": (s.date, s.start_time or dt_time.min),
                },
            )
    rows = sorted(rows_by_session.values(), key=lambda r: r["sort_key"])
    for r in rows:
        del r["sort_key"]
    return rows


def _account_summary(children):
    """Balance / volunteer / documents are stubs until real models ship.
    Returning an explicit shape (with None defaults) keeps the template
    honest — the Account tab shows 'Not tracked yet' rather than a fake
    zero balance."""
    return {
        "balance": None,           # decimal | None
        "balance_status": None,    # 'paid' | 'due' | None
        "volunteer_status": None,  # 'fulfilled' | 'open' | None
        "volunteer_hours_open": None,
        "documents": [],           # [{name, status, expires}] when model lands
        "children_count": len(children),
    }


def _inbox_rows(children, limit=20):
    """EmailLog entries for any of the parent's children, most recent
    first. Each row shows the subject, when, and which child it was about
    so a parent with two kids can tell them apart at a glance."""
    if not children:
        return []
    logs = (
        EmailLog.objects
        .filter(player_season__in=children)
        .select_related("player_season__player")
        .order_by("-sent_at")[:limit]
    )
    return [
        {
            "id": log.id,
            "subject": log.subject,
            "preview": (log.body_snapshot or "")[:120],
            "child_name": log.player_season.player.first_name,
            "when": timezone.localtime(log.sent_at).strftime("%b %-d · %-I:%M %p"),
            "delivered": bool(log.delivered_at),
            "bounced": bool(log.bounced),
        }
        for log in logs
    ]


# ─── Views ─────────────────────────────────────────────────────────────────


@login_required
def parent_index(request):
    """Bare /parent/ → redirect to Today so the URL is shareable."""
    return HttpResponseRedirect(reverse("parent_today"))


@login_required
def parent_today(request):
    active_season = _get_active_season()
    children = list(_children_for_user(request.user, active_season))
    cards = _player_cards(children)

    # One next-event block per child. Two-child families see two cards;
    # a parent with no matched PlayerSeason sees the empty state.
    for card in cards:
        ps = next((c for c in children if c.id == card["id"]), None)
        card["next_event"] = _next_event_for_child(ps)

    context = {
        "parent_active": "today",
        "greeting": _greeting(),
        "today_label": timezone.now().date().strftime("%A · %b %-d"),
        "user_first_name": request.user.first_name or request.user.get_username(),
        "player_cards": cards,
        "has_children": bool(cards),
    }
    return render(request, "parent/today.html", context)


@login_required
def parent_schedule(request):
    active_season = _get_active_season()
    children = list(_children_for_user(request.user, active_season))
    rows = _upcoming_schedule(children)

    context = {
        "parent_active": "schedule",
        "child_names": [c.player.first_name for c in children],
        "schedule_rows": rows,
        "schedule_count": len(rows),
        "has_children": bool(children),
    }
    return render(request, "parent/schedule.html", context)


@login_required
def parent_account(request):
    active_season = _get_active_season()
    children = list(_children_for_user(request.user, active_season))
    cards = _player_cards(children)
    summary = _account_summary(children)

    context = {
        "parent_active": "account",
        "user_email": request.user.email,
        "user_phone": getattr(request.user, "phone", "") or "",
        "player_cards": cards,
        "account_summary": summary,
        "has_children": bool(cards),
    }
    return render(request, "parent/account.html", context)


@login_required
def parent_inbox(request):
    active_season = _get_active_season()
    children = list(_children_for_user(request.user, active_season))
    rows = _inbox_rows(children)

    context = {
        "parent_active": "inbox",
        "inbox_rows": rows,
        "inbox_count": len(rows),
        "has_children": bool(children),
    }
    return render(request, "parent/inbox.html", context)
