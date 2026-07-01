from collections import Counter
from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_GET, require_POST

from accounts.models import CoachSeason
from tryouts.models import Session

from .models import Division, PlayerSeason, Season, Station, TeamSeason


@login_required
def index(request):
    """Roster — Pacific token-driven list with division chips, sub-league /
    Top-4 / Unassigned view toggle, and name search.

    Honours `?q=<name>` (plain or 'Last, First' format) and `?account=<account_name>`
    so the SFLL-117 ⌘K palette can deep-link into a filtered view.
    """
    active_season = Season.objects.filter(is_active=True).first()

    qs = (
        PlayerSeason.objects.select_related(
            "player", "division", "assigned_team__team"
        ).filter(season=active_season)
        if active_season
        else PlayerSeason.objects.none()
    )

    divisions = list(Division.objects.filter(is_active=True))

    division_param = request.GET.get("division", "")
    selected_division = next(
        (d for d in divisions if str(d.id) == division_param),
        None,
    )
    if selected_division:
        qs = qs.filter(division=selected_division)

    sub_leagues = (
        list(selected_division.league_names)
        if selected_division and selected_division.has_leagues
        else []
    )
    league_param = request.GET.get("league", "")
    if league_param and league_param in sub_leagues:
        qs = qs.filter(assigned_team__sub_league=league_param)

    view_param = request.GET.get("view", "all")
    if view_param == "top4":
        qs = qs.filter(is_top_4=True)
    elif view_param == "unassigned":
        qs = qs.filter(assigned_team__isnull=True)
    else:
        view_param = "all"

    q = (request.GET.get("q") or "").strip()
    account = (request.GET.get("account") or "").strip()
    if q:
        if "," in q:
            # "Last, First" format produced by the command-palette deep-links.
            last_part, _, first_part = q.partition(",")
            qs = qs.filter(
                Q(player__last_name__icontains=last_part.strip())
                & Q(player__first_name__icontains=first_part.strip())
            )
        else:
            qs = qs.filter(
                Q(player__first_name__icontains=q) | Q(player__last_name__icontains=q)
            )
    if account:
        qs = qs.filter(account_name=account)

    player_count = qs.count()
    page_obj = Paginator(qs, 50).get_page(request.GET.get("page", 1))

    # Strip ?page= from the current querystring so pagination links can
    # append their own page number without doubling it.
    params = request.GET.copy()
    params.pop("page", None)
    filter_qs = params.urlencode()

    return render(
        request,
        "players/index.html",
        {
            "player_seasons": page_obj,
            "player_count": player_count,
            "page_obj": page_obj,
            "filter_qs": filter_qs,
            "season": active_season,
            "divisions": divisions,
            "sub_leagues": sub_leagues,
            "selected_division": selected_division,
            "selected_league": league_param if league_param in sub_leagues else "",
            "view": view_param,
            "q": q,
            "roster_query": q,
            "roster_account": account,
        },
    )


@login_required
def teams(request):
    """Team list for the active season."""
    active_season = Season.objects.filter(is_active=True).first()
    team_seasons = (
        TeamSeason.objects.select_related(
            "team",
            "division",
        ).filter(season=active_season)
        if active_season
        else TeamSeason.objects.none()
    )

    return render(
        request,
        "players/teams.html",
        {
            "team_seasons": team_seasons,
            "season": active_season,
        },
    )


@login_required
def dugout_card(request, pk):
    """Printable half-sheet dugout card for a single TeamSeason.

    Schedule + per-player emergency phones are blank fill-in rows: SFLL
    doesn't store games or guardian phone numbers yet, and coaches who
    actually print this expect to ink those in field-side.
    """
    team_season = get_object_or_404(
        TeamSeason.objects.select_related("team", "division", "season"),
        pk=pk,
    )
    roster = (
        PlayerSeason.objects.select_related("player")
        .filter(assigned_team=team_season)
        .order_by("player__last_name", "player__first_name")
    )

    return render(
        request,
        "players/dugout_card.html",
        {
            "team_season": team_season,
            "roster": roster,
            "schedule_slots": range(5),
        },
    )


# ── Print surfaces — SFLL-114 (Phase 9) ────────────────────────────────────


@login_required
def print_index(request):
    """Index listing every team in the active season with a Print card link.

    Grouped by division + sub-league so a manager can scan quickly before
    a game day. Lives at /players/print/ alongside the other roster surfaces.
    """
    active_season = Season.objects.filter(is_active=True).first()
    team_seasons = (
        TeamSeason.objects.select_related("team", "division")
        .filter(season=active_season)
        .order_by("division__display_order", "sub_league", "team__name")
        if active_season
        else TeamSeason.objects.none()
    )
    return render(
        request,
        "players/print_index.html",
        {
            "team_seasons": team_seasons,
            "season": active_season,
        },
    )


@login_required
def print_dugout_card(request, team_season_id):
    """Half-sheet dugout roster card — standalone print surface.

    Renders a print-only page (no app shell) with two identical half-sheet
    cards stacked on one letter sheet. The browser print dialog fires on
    load; pass ?print=0 to suppress when proofing layout on screen.

    Each card carries:
    - Team strip: team name + division + head/assistant coaches with phone
    - Next 5 sessions in the team's division (stand-in for a Game model)
    - Roster with parent/guardian name + emergency contact emails
    """
    team_season = get_object_or_404(
        TeamSeason.objects.select_related("team__league", "season__league", "division"),
        pk=team_season_id,
    )

    coach_seasons = list(
        CoachSeason.objects.filter(team_season=team_season)
        .select_related("coach__user")
        .order_by("role", "coach__user__last_name")
    )
    head_coach = next((cs for cs in coach_seasons if cs.role == "head_coach"), None)
    assistant_coaches = [cs for cs in coach_seasons if cs.role == "assistant_coach"]

    roster = list(
        PlayerSeason.objects.filter(assigned_team=team_season)
        .select_related("player")
        .order_by("player__last_name", "player__first_name")
    )

    # Sessions stand in for a Game model until that lands — same placeholder
    # pattern Phase 8 used. Filter to the team's division, current season,
    # future-only, limit to the next 5. Season filter prevents sessions from
    # other seasons sharing the same division from leaking onto the card.
    today = timezone.localdate()
    games = list(
        Session.objects.filter(
            division=team_season.division, season=team_season.season, date__gte=today
        ).order_by("date", "start_time")[:5]
    )

    auto_print = request.GET.get("print", "1") != "0"

    return render(
        request,
        "players/print_dugout_card.html",
        {
            "team_season": team_season,
            "head_coach": head_coach,
            "assistant_coaches": assistant_coaches,
            "roster": roster,
            "games": games,
            "auto_print": auto_print,
        },
    )


# ---------------------------------------------------------------------------
# Player Detail (SFLL-109 — Phase 4)
# ---------------------------------------------------------------------------

EDITABLE_FIELDS = {
    "first_name",
    "last_name",
    "date_of_birth",
    "jersey_number",
    "assigned_team",
    "sub_league",
}


def _user_can_edit_roster(user, player_season):
    """Edits on the detail page require admin-equivalent role scoped to the
    player's league.

    Global roles (cto, ses_manager, vp_player_agents, president) are scoped to
    the target player's league — an admin from another league cannot edit this
    player. player_agent is additionally scoped to the target player's division.
    """
    if user.is_staff or user.is_superuser:
        return True
    league = player_season.season.league
    roles = user.roles.filter(is_active=True, league=league)
    if roles.filter(
        role__in=["cto", "ses_manager", "vp_player_agents", "president"]
    ).exists():
        return True
    division = player_season.division
    if division and roles.filter(role="player_agent", division=division).exists():
        return True
    return False


def _can_view_evals(user, division=None):
    """Mirrors evaluations._can_view_aggregated — aggregated only, never per-coach."""
    if user.is_superuser:
        return True
    roles = user.roles.filter(is_active=True)
    if roles.filter(
        role__in=["cto", "ses_manager", "vp_player_agents", "president"]
    ).exists():
        return True
    if division and roles.filter(role="player_agent", division=division).exists():
        return True
    return False


def _composite_score(player_season):
    """Compute station-by-station composite scores for the Evals tab.

    Returns a list of dicts ordered by Station.display_order. Privacy: averaged
    across all coaches; we never expose per-coach values from this surface.
    """
    from evaluations.models import Evaluation  # local import to avoid cycle

    season = player_season.season
    stations = list(
        Station.objects.filter(league=season.league, is_active=True).order_by(
            "display_order",
        ),
    )
    evals = Evaluation.objects.filter(player_season=player_season).select_related(
        "station",
        "session",
        "coach_season",
    )

    rows = []
    station_total = 0.0
    station_count = 0
    for station in stations:
        station_evals = [e for e in evals if e.station_id == station.id]
        coach_count = len({e.coach_season_id for e in station_evals})

        field_cells = []
        all_scores_for_station = []
        for field_def in station.eval_fields or []:
            key = field_def["key"]
            values = []
            for ev in station_evals:
                val = (ev.scores or {}).get(key)
                if isinstance(val, (int, float)):
                    values.append(val)
            cell = {
                "label": field_def.get("label", key),
                "key": key,
                "avg": round(sum(values) / len(values), 1) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "count": len(values),
            }
            field_cells.append(cell)
            all_scores_for_station.extend(values)

        station_avg = (
            round(sum(all_scores_for_station) / len(all_scores_for_station), 1)
            if all_scores_for_station
            else None
        )
        rows.append(
            {
                "station": station,
                "field_cells": field_cells,
                "station_avg": station_avg,
                "coach_count": coach_count,
                "has_data": bool(station_evals),
            }
        )
        if station_avg is not None:
            station_total += station_avg
            station_count += 1

    overall = round(station_total / station_count, 1) if station_count else None

    return {
        "stations": rows,
        "overall": overall,
    }


@login_required
def player_detail(request, player_season_id):
    """Player Detail — Overview / Season / Evals tabs."""
    player_season = get_object_or_404(
        PlayerSeason.objects.select_related(
            "player",
            "division",
            "season__league",
            "assigned_team__team",
            "assigned_team__division",
            "coaches_child_of__coach__user",
        ),
        pk=player_season_id,
    )

    active_tab = request.GET.get("tab") or "overview"
    if active_tab not in {"overview", "season", "evals"}:
        active_tab = "overview"

    can_edit = _user_can_edit_roster(request.user, player_season)

    # Teams the user can reassign this player to within the same division.
    available_teams = (
        TeamSeason.objects.filter(
            season=player_season.season,
            division=player_season.division,
        )
        .select_related("team")
        .order_by("team__name")
        if player_season.division
        else (TeamSeason.objects.none())
    )

    sub_league_choices = []
    if player_season.division and player_season.division.has_leagues:
        sub_league_choices = list(player_season.division.league_names or [])

    composite = None
    can_see_evals = _can_view_evals(request.user, division=player_season.division)
    if can_see_evals:
        composite = _composite_score(player_season)

    # Session attendance / objective metrics for the Season tab.
    session_assignments = player_season.session_assignments.select_related(
        "session",
    ).order_by("session__date")
    sessions_rows = []
    for sa in session_assignments:
        checkin = getattr(sa, "checkin", None)
        sessions_rows.append(
            {
                "session": sa.session,
                "checked_in_at": checkin.checked_in_at if checkin else None,
                "no_show": checkin is None and sa.session.date < date.today(),
            }
        )

    return render(
        request,
        "players/detail.html",
        {
            "ps": player_season,
            "active_tab": active_tab,
            "can_edit": can_edit,
            "can_see_evals": can_see_evals,
            "composite": composite,
            "sessions_rows": sessions_rows,
            "available_teams": available_teams,
            "sub_league_choices": sub_league_choices,
        },
    )


# ---------------------------------------------------------------------------
# HTMX inline-edit endpoints
# ---------------------------------------------------------------------------


def _field_partial(request, ps, field):
    """Render the read-mode partial for a single field."""
    return render(
        request,
        "players/_partials/detail_field.html",
        {"ps": ps, "field": field, "can_edit": _user_can_edit_roster(request.user, ps)},
    )


def _edit_partial(request, ps, field):
    """Render the edit-mode partial (input/select) for a single field."""
    extra = {}
    if field == "assigned_team":
        extra["available_teams"] = (
            TeamSeason.objects.filter(
                season=ps.season,
                division=ps.division,
            )
            .select_related("team")
            .order_by("team__name")
            if ps.division
            else (TeamSeason.objects.none())
        )
    elif field == "sub_league":
        choices = []
        if ps.division and ps.division.has_leagues:
            choices = list(ps.division.league_names or [])
        extra["sub_league_choices"] = choices
    return render(
        request,
        "players/_partials/detail_field_edit.html",
        {"ps": ps, "field": field, **extra},
    )


@login_required
@require_GET
def detail_field(request, player_season_id, field):
    """Return the read-mode cell (used to cancel an in-progress edit)."""
    if field not in EDITABLE_FIELDS:
        return HttpResponseBadRequest("Unknown field.")
    ps = get_object_or_404(
        PlayerSeason.objects.select_related(
            "player", "season__league", "assigned_team__team"
        ),
        pk=player_season_id,
    )
    return _field_partial(request, ps, field)


@login_required
@require_GET
def detail_field_edit(request, player_season_id, field):
    """Return the edit-mode cell (input/select) on first click."""
    if field not in EDITABLE_FIELDS:
        return HttpResponseBadRequest("Unknown field.")
    ps = get_object_or_404(
        PlayerSeason.objects.select_related(
            "player", "division", "season__league", "assigned_team__team"
        ),
        pk=player_season_id,
    )
    if not _user_can_edit_roster(request.user, ps):
        return HttpResponseForbidden("Editing roster fields requires admin role.")
    return _edit_partial(request, ps, field)


@login_required
@require_POST
def detail_field_save(request, player_season_id, field):
    """Persist an inline edit and return the read-mode cell."""
    if field not in EDITABLE_FIELDS:
        return HttpResponseBadRequest("Unknown field.")

    ps = get_object_or_404(
        PlayerSeason.objects.select_related(
            "player", "division", "season__league", "assigned_team__team"
        ),
        pk=player_season_id,
    )
    if not _user_can_edit_roster(request.user, ps):
        return HttpResponseForbidden("Editing roster fields requires admin role.")
    raw = (request.POST.get("value") or "").strip()

    try:
        if field == "first_name":
            if not raw:
                return HttpResponseBadRequest("First name cannot be empty.")
            ps.player.first_name = raw
            ps.player.save(update_fields=["first_name", "updated_at"])
        elif field == "last_name":
            if not raw:
                return HttpResponseBadRequest("Last name cannot be empty.")
            ps.player.last_name = raw
            ps.player.save(update_fields=["last_name", "updated_at"])
        elif field == "date_of_birth":
            if raw:
                try:
                    ps.player.date_of_birth = datetime.strptime(raw, "%Y-%m-%d").date()
                except ValueError:
                    return HttpResponseBadRequest("DOB must be YYYY-MM-DD.")
            else:
                ps.player.date_of_birth = None
            ps.player.save(update_fields=["date_of_birth", "updated_at"])
        elif field == "jersey_number":
            if raw:
                try:
                    n = int(raw)
                except ValueError:
                    return HttpResponseBadRequest("Jersey number must be an integer.")
                if n < 0 or n > 999:
                    return HttpResponseBadRequest("Jersey number out of range.")
                ps.jersey_number = n
            else:
                ps.jersey_number = None
            ps.save(update_fields=["jersey_number", "updated_at"])
        elif field == "assigned_team":
            if raw:
                try:
                    ts = TeamSeason.objects.select_related("team").get(
                        pk=raw,
                        season=ps.season,
                    )
                except (TeamSeason.DoesNotExist, ValueError):
                    return HttpResponseBadRequest("Unknown team for this season.")
                if ps.division_id and ts.division_id != ps.division_id:
                    return HttpResponseBadRequest(
                        "Team is not in the player's division."
                    )
                ps.assigned_team = ts
            else:
                ps.assigned_team = None
            ps.save(update_fields=["assigned_team", "updated_at"])
            # refresh related cache so the template renders the new team name
            ps = PlayerSeason.objects.select_related(
                "player",
                "assigned_team__team",
            ).get(pk=ps.pk)
        elif field == "sub_league":
            ts = ps.assigned_team
            if ts is None:
                return HttpResponseBadRequest(
                    "Assign a team before setting a sub-league.",
                )
            allowed = (
                list((ps.division.league_names or []))
                if (ps.division and ps.division.has_leagues)
                else []
            )
            if raw and allowed and raw not in allowed:
                return HttpResponseBadRequest(
                    "Sub-league not configured for this division."
                )
            ts.sub_league = raw
            ts.save(update_fields=["sub_league", "updated_at"])
    except Exception as exc:  # noqa: BLE001 — surface message to HTMX
        return HttpResponseBadRequest(str(exc))

    return _field_partial(request, ps, field)


# ---------------------------------------------------------------------------
# Family — SFLL-95 (Phase 4)
#
# A "family" is the set of PlayerSeasons in the active season that share an
# account_email (the SportsConnect payer). No Family model yet; identity is
# the email, URL-encoded with urlsafe-b64 so it round-trips cleanly in paths.
# Real models for Balance and VolunteerObligation land in later phases — the
# detail page surfaces structured empty shells today so the treasurer +
# division-coordinator workflows have a stable place to land once data exists.
# ---------------------------------------------------------------------------

FAMILY_COMMS_LIMIT = 20

# Roles that may access family-level data (contacts, comms, balance).
_FAMILY_ACCESS_ROLES = (
    "cto",
    "ses_manager",
    "vp_player_agents",
    "president",
    "player_agent",
    "treasurer",
)


def encode_family_key(email):
    """Stable, URL-safe handle for a family (currently their account email)."""
    return urlsafe_base64_encode((email or "").strip().lower().encode())


def _decode_family_key(family_key):
    try:
        return urlsafe_base64_decode(family_key).decode()
    except (ValueError, UnicodeDecodeError):
        raise Http404("Unknown family")


def _user_has_role(user, *role_names, league=None):
    if user.is_superuser:
        return True
    qs = user.roles.filter(is_active=True, role__in=role_names)
    if league is not None:
        qs = qs.filter(league=league)
    return qs.exists()


def _treasurer_view_only(user, league=None):
    """True if this user can see balances but not edit anything else.

    Treasurers handle dues and outstanding balances; admin/finance edits are
    out-of-scope for the family detail page until a real Balance model lands.
    Scoped to `league` when provided so a treasurer on a different League
    does not get visibility into this family's balance.
    """
    if user.is_superuser:
        return False
    role_qs = user.roles.filter(is_active=True)
    if league is not None:
        role_qs = role_qs.filter(league=league)
    roles = set(role_qs.values_list("role", flat=True))
    admin_roles = {
        "cto",
        "ses_manager",
        "vp_player_agents",
        "president",
        "player_agent",
    }
    return "treasurer" in roles and not (roles & admin_roles)


@login_required
def family_index(request):
    """List all families in the active season, ordered by account name.

    Built off PlayerSeason.account_email grouping rather than a dedicated
    Family table — that import path already exists from SportsConnect and we
    don't want to invent a new entity until it earns its keep.
    """
    active_season = Season.objects.filter(is_active=True).first()
    # Scope the role check to the active season's league so a user with a
    # qualifying role in a different league cannot enumerate this season's
    # families (SFLL-146).
    league = active_season.league if active_season else None
    if not _user_has_role(request.user, *_FAMILY_ACCESS_ROLES, league=league):
        raise PermissionDenied
    if not active_season:
        return render(
            request,
            "players/family_index.html",
            {
                "families": [],
                "season": None,
            },
        )

    rows = (
        PlayerSeason.objects.filter(season=active_season)
        .exclude(account_email="")
        .values("account_email", "account_name")
        .annotate(player_count=Count("id"))
        .order_by("account_name", "account_email")
    )

    # Same email may show under slightly different account_names across
    # registrations; pick the most common name per email.
    grouped = {}
    for row in rows:
        email = (row["account_email"] or "").lower()
        entry = grouped.setdefault(
            email,
            {
                "email": email,
                "names": Counter(),
                "player_count": 0,
            },
        )
        entry["names"][row["account_name"] or "(no name)"] += row["player_count"]
        entry["player_count"] += row["player_count"]

    families = []
    for email, entry in grouped.items():
        name = entry["names"].most_common(1)[0][0]
        families.append(
            {
                "email": email,
                "name": name,
                "player_count": entry["player_count"],
                "family_key": encode_family_key(email),
            }
        )
    families.sort(key=lambda f: (f["name"].lower(), f["email"]))

    return render(
        request,
        "players/family_index.html",
        {
            "families": families,
            "season": active_season,
        },
    )


@login_required
def family_detail(request, family_key):
    """Family detail — players, contacts, balance, volunteer obligations, comms.

    Sections that don't yet have backing models (Balance, VolunteerObligation)
    render as structured empty shells. The treasurer role flips the page into
    read-only mode — same surface, no edit affordances.
    """
    email = _decode_family_key(family_key).lower()
    if not email:
        raise Http404("Unknown family")

    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        raise Http404("No active season")

    if not _user_has_role(
        request.user, *_FAMILY_ACCESS_ROLES, league=active_season.league
    ):
        raise PermissionDenied

    player_seasons = list(
        PlayerSeason.objects.filter(season=active_season, account_email__iexact=email)
        .select_related(
            "player",
            "division",
            "assigned_team__team",
            "assigned_team__division",
        )
        .order_by("player__last_name", "player__first_name")
    )
    if not player_seasons:
        raise Http404("No players in this family")

    # Account name: pick the most common spelling across siblings.
    name_counter = Counter(
        (ps.account_name or "").strip() for ps in player_seasons if ps.account_name
    )
    account_name = name_counter.most_common(1)[0][0] if name_counter else email

    # Contacts grid — derived from the SportsConnect payload (account_email +
    # additional_email). Emergency contact has no model field yet; surface a
    # placeholder so the slot is visible.
    additional_emails = [
        ps.additional_email for ps in player_seasons if ps.additional_email
    ]
    secondary_email = next(iter(dict.fromkeys(additional_emails)), "")
    contacts = [
        {
            "role": "Primary parent",
            "role_badge": "primary",
            "name": account_name,
            "email": email,
            "phone": "",
            "is_placeholder": False,
        },
        {
            "role": "Secondary contact",
            "role_badge": "secondary",
            "name": "",
            "email": secondary_email,
            "phone": "",
            "is_placeholder": not secondary_email,
        },
        {
            "role": "Emergency contact",
            "role_badge": "emergency",
            "name": "",
            "email": "",
            "phone": "",
            "is_placeholder": True,
        },
    ]

    # Division-level volunteer policy — division.name is enough context for
    # now; per-division pledged hours live in a config table that doesn't
    # exist yet. Surface what we know plus the empty shell.
    division_names = sorted({ps.division.name for ps in player_seasons if ps.division})

    # Comms history — last N outbound emails to any sibling in this family.
    # Pulled fresh from EmailLog so the family page becomes the audit surface
    # for "did we send them the SES reminder?"
    from communications.models import EmailLog  # local import to avoid cycle

    comms_rows = list(
        EmailLog.objects.filter(player_season__in=player_seasons)
        .select_related("player_season__player", "template")
        .order_by("-sent_at")[:FAMILY_COMMS_LIMIT]
    )

    league = active_season.league
    treasurer_only = _treasurer_view_only(request.user, league=league)
    is_admin = _user_has_role(
        request.user,
        "cto",
        "ses_manager",
        "vp_player_agents",
        "president",
        "player_agent",
        league=league,
    )
    can_see_balance = treasurer_only or is_admin

    return render(
        request,
        "players/family_detail.html",
        {
            "email": email,
            "family_key": family_key,
            "account_name": account_name,
            "player_seasons": player_seasons,
            "contacts": contacts,
            "division_names": division_names,
            "comms_rows": comms_rows,
            "season": active_season,
            "treasurer_only": treasurer_only,
            "can_see_balance": can_see_balance,
            "comms_limit": FAMILY_COMMS_LIMIT,
        },
    )
