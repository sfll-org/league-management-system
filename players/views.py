import urllib.parse
from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.models import CoachSeason
from tryouts.models import Session

from .models import Division, PlayerSeason, Season, Station, TeamSeason


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------

@login_required
def index(request):
    """Player roster — Pacific-shell list with filter chips + link to detail."""
    active_season = Season.objects.filter(is_active=True).first()

    qs = PlayerSeason.objects.select_related(
        'player', 'division', 'assigned_team__team',
    )
    if active_season:
        qs = qs.filter(season=active_season)
    else:
        qs = PlayerSeason.objects.none()

    division_id = request.GET.get('division')
    selected_division = None
    if division_id:
        qs = qs.filter(division_id=division_id)
        selected_division = Division.objects.filter(pk=division_id, is_active=True).first()

    # Sub-league chips — only when the active division splits into sub-leagues.
    sub_leagues = []
    selected_league = ''
    if selected_division and selected_division.has_leagues:
        sub_leagues = list(selected_division.league_names or [])
        selected_league = request.GET.get('league', '')
        if selected_league and selected_league in sub_leagues:
            qs = qs.filter(assigned_team__sub_league=selected_league)
        else:
            selected_league = ''

    view = request.GET.get('view', 'all')
    if view == 'top4':
        qs = qs.filter(is_top_4=True)
    elif view == 'unassigned':
        qs = qs.filter(assigned_team__isnull=True)

    search = (request.GET.get('q') or '').strip()
    if search:
        qs = qs.filter(player__last_name__icontains=search) | qs.filter(
            player__first_name__icontains=search,
        )

    _sort_map = {
        'name':     ['player__last_name', 'player__first_name'],
        'division': ['division__display_order', 'division__name'],
        'team':     ['assigned_team__team__name'],
        'jersey':   ['jersey_number'],
        'status':   ['status'],
    }
    sort = request.GET.get('sort', 'name')
    if sort not in _sort_map:
        sort = 'name'
    sort_dir = request.GET.get('dir', 'asc')
    if sort_dir not in ('asc', 'desc'):
        sort_dir = 'asc'
    order_fields = _sort_map[sort]
    if sort_dir == 'desc':
        order_fields = [f'-{f}' for f in order_fields]

    # Querystring for sort links (preserves q/view/division/league, strips sort/dir).
    base_params = {k: v for k, v in request.GET.items() if k not in ('sort', 'dir')}
    sort_base_qs = urllib.parse.urlencode(base_params)

    return render(request, 'players/index.html', {
        'player_seasons': qs.order_by(*order_fields),
        'season': active_season,
        'divisions': Division.objects.filter(is_active=True),
        'division_id': division_id,
        'sub_leagues': sub_leagues,
        'selected_league': selected_league,
        'view': view,
        'search': search,
        'sort': sort,
        'sort_dir': sort_dir,
        'sort_base_qs': sort_base_qs,
    })


@login_required
def teams(request):
    """Team list for the active season."""
    active_season = Season.objects.filter(is_active=True).first()
    team_seasons = TeamSeason.objects.select_related(
        'team', 'division',
    ).filter(season=active_season) if active_season else TeamSeason.objects.none()

    return render(request, 'players/teams.html', {
        'team_seasons': team_seasons,
        'season': active_season,
    })


# ─── Print surfaces (SFLL-114, Phase 9) ───────────────────────────────────


@login_required
def print_index(request):
    """Index of teams that have a dugout card available to print.

    Lists every TeamSeason in the active season, grouped by division and
    sub-league. Each row deep-links to the half-sheet dugout card surface.
    Lives at /players/print/ so it sits next to the team / roster surfaces
    a manager already touches.
    """
    active_season = Season.objects.filter(is_active=True).first()
    team_seasons = (
        TeamSeason.objects.select_related('team', 'division')
        .filter(season=active_season)
        .order_by('division__display_order', 'sub_league', 'team__name')
        if active_season else TeamSeason.objects.none()
    )
    return render(request, 'players/print_index.html', {
        'team_seasons': team_seasons,
        'season': active_season,
    })


@login_required
def print_dugout_card(request, team_season_id):
    """Half-sheet dugout roster card for a single team.

    Renders a print-only surface (no app shell) and fires the browser print
    dialog on load. Two cards fit on a letter sheet under the @page rules
    in lms-components.css. Sessions stand in for a Game model until that
    lands — same placeholder pattern Phase 8 used in core/field_views.py,
    so the surface renders against real data where it exists and degrades
    cleanly where it does not. Pass ?print=0 to suppress the auto-print
    handoff (useful when proofing the layout on screen).
    """
    team_season = get_object_or_404(
        TeamSeason.objects.select_related('team__league', 'season', 'division'),
        pk=team_season_id,
    )

    coach_seasons = (
        CoachSeason.objects.filter(team_season=team_season)
        .select_related('coach__user')
        .order_by('role', 'coach__user__last_name')
    )
    head_coach = next((cs for cs in coach_seasons if cs.role == 'head_coach'), None)
    assistant_coaches = [cs for cs in coach_seasons if cs.role == 'assistant_coach']

    roster = (
        PlayerSeason.objects.filter(assigned_team=team_season)
        .select_related('player')
        .order_by('player__last_name', 'player__first_name')
    )

    today = timezone.now().date()
    games = list(
        Session.objects.filter(
            season=team_season.season,
            division=team_season.division,
            date__gte=today,
        ).order_by('date', 'start_time')[:5]
    )

    return render(request, 'players/print_dugout_card.html', {
        'team_season': team_season,
        'head_coach': head_coach,
        'assistant_coaches': assistant_coaches,
        'roster': roster,
        'games': games,
        'league': team_season.team.league,
        'auto_print': request.GET.get('print') != '0',
    })


# ---------------------------------------------------------------------------
# Player Detail (SFLL-94 — Phase 4)
# ---------------------------------------------------------------------------

EDITABLE_FIELDS = {
    'first_name', 'last_name', 'date_of_birth',
    'jersey_number', 'assigned_team', 'sub_league',
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
    if roles.filter(role__in=['cto', 'ses_manager', 'vp_player_agents', 'president']).exists():
        return True
    division = player_season.division
    if division and roles.filter(role='player_agent', division=division).exists():
        return True
    return False


def _can_view_evals(user, division=None, league=None):
    """Mirrors evaluations._can_view_aggregated — aggregated only, never per-coach.

    Roles are scoped to `league` so a CTO of league A cannot view league B evals.
    """
    if user.is_superuser:
        return True
    roles = user.roles.filter(is_active=True)
    if league:
        roles = roles.filter(league=league)
    if roles.filter(role__in=['cto', 'ses_manager', 'vp_player_agents', 'president']).exists():
        return True
    if division and roles.filter(role='player_agent', division=division).exists():
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
            'display_order',
        ),
    )
    evals = Evaluation.objects.filter(player_season=player_season).select_related(
        'station', 'session', 'coach_season',
    )

    rows = []
    station_total = 0.0
    station_count = 0
    for station in stations:
        station_evals = [e for e in evals if e.station_id == station.id]
        coach_count = len({e.coach_season_id for e in station_evals})

        field_cells = []
        all_scores_for_station = []
        for field_def in (station.eval_fields or []):
            key = field_def['key']
            values = []
            for ev in station_evals:
                val = (ev.scores or {}).get(key)
                if isinstance(val, (int, float)):
                    values.append(val)
            cell = {
                'label': field_def.get('label', key),
                'key': key,
                'avg': round(sum(values) / len(values), 1) if values else None,
                'min': min(values) if values else None,
                'max': max(values) if values else None,
                'count': len(values),
            }
            field_cells.append(cell)
            all_scores_for_station.extend(values)

        station_avg = (
            round(sum(all_scores_for_station) / len(all_scores_for_station), 1)
            if all_scores_for_station
            else None
        )
        rows.append({
            'station': station,
            'field_cells': field_cells,
            'station_avg': station_avg,
            'coach_count': coach_count,
            'has_data': bool(station_evals),
        })
        if station_avg is not None:
            station_total += station_avg
            station_count += 1

    overall = round(station_total / station_count, 1) if station_count else None

    return {
        'stations': rows,
        'overall': overall,
    }


@login_required
def player_detail(request, player_season_id):
    """Player Detail — Overview / Season / Evals tabs."""
    player_season = get_object_or_404(
        PlayerSeason.objects.select_related(
            'player', 'division', 'season__league', 'assigned_team__team',
            'assigned_team__division', 'coaches_child_of__coach__user',
        ),
        pk=player_season_id,
    )

    active_tab = request.GET.get('tab') or 'overview'
    if active_tab not in {'overview', 'season', 'evals'}:
        active_tab = 'overview'

    can_edit = _user_can_edit_roster(request.user, player_season)

    # Teams the user can reassign this player to within the same division.
    available_teams = TeamSeason.objects.filter(
        season=player_season.season,
        division=player_season.division,
    ).select_related('team').order_by('team__name') if player_season.division else (
        TeamSeason.objects.none()
    )

    sub_league_choices = []
    if player_season.division and player_season.division.has_leagues:
        sub_league_choices = list(player_season.division.league_names or [])

    composite = None
    can_see_evals = _can_view_evals(
        request.user,
        division=player_season.division,
        league=player_season.season.league,
    )
    if can_see_evals:
        composite = _composite_score(player_season)

    # Session attendance / objective metrics for the Season tab.
    session_assignments = player_season.session_assignments.select_related(
        'session',
    ).order_by('session__date')
    sessions_rows = []
    for sa in session_assignments:
        checkin = getattr(sa, 'checkin', None)
        sessions_rows.append({
            'session': sa.session,
            'checked_in_at': checkin.checked_in_at if checkin else None,
            'no_show': checkin is None and sa.session.date < date.today(),
        })

    return render(request, 'players/detail.html', {
        'ps': player_season,
        'active_tab': active_tab,
        'can_edit': can_edit,
        'can_see_evals': can_see_evals,
        'composite': composite,
        'sessions_rows': sessions_rows,
        'available_teams': available_teams,
        'sub_league_choices': sub_league_choices,
    })


# ---------------------------------------------------------------------------
# HTMX inline-edit endpoints
# ---------------------------------------------------------------------------

def _field_partial(request, ps, field):
    """Render the read-mode partial for a single field."""
    return render(
        request,
        'players/_partials/detail_field.html',
        {'ps': ps, 'field': field, 'can_edit': _user_can_edit_roster(request.user, ps)},
    )


def _edit_partial(request, ps, field):
    """Render the edit-mode partial (input/select) for a single field."""
    extra = {}
    if field == 'assigned_team':
        extra['available_teams'] = TeamSeason.objects.filter(
            season=ps.season,
            division=ps.division,
        ).select_related('team').order_by('team__name') if ps.division else (
            TeamSeason.objects.none()
        )
    elif field == 'sub_league':
        choices = []
        if ps.division and ps.division.has_leagues:
            choices = list(ps.division.league_names or [])
        extra['sub_league_choices'] = choices
    return render(
        request,
        'players/_partials/detail_field_edit.html',
        {'ps': ps, 'field': field, **extra},
    )


@login_required
@require_GET
def detail_field(request, player_season_id, field):
    """Return the read-mode cell (used to cancel an in-progress edit)."""
    if field not in EDITABLE_FIELDS:
        return HttpResponseBadRequest('Unknown field.')
    ps = get_object_or_404(
        PlayerSeason.objects.select_related('player', 'season__league', 'assigned_team__team'),
        pk=player_season_id,
    )
    return _field_partial(request, ps, field)


@login_required
@require_GET
def detail_field_edit(request, player_season_id, field):
    """Return the edit-mode cell (input/select) on first click."""
    if field not in EDITABLE_FIELDS:
        return HttpResponseBadRequest('Unknown field.')
    ps = get_object_or_404(
        PlayerSeason.objects.select_related('player', 'division', 'season__league', 'assigned_team__team'),
        pk=player_season_id,
    )
    if not _user_can_edit_roster(request.user, ps):
        return HttpResponseForbidden('Editing roster fields requires admin role.')
    return _edit_partial(request, ps, field)


@login_required
@require_POST
def detail_field_save(request, player_season_id, field):
    """Persist an inline edit and return the read-mode cell."""
    if field not in EDITABLE_FIELDS:
        return HttpResponseBadRequest('Unknown field.')

    ps = get_object_or_404(
        PlayerSeason.objects.select_related('player', 'division', 'season__league', 'assigned_team__team'),
        pk=player_season_id,
    )
    if not _user_can_edit_roster(request.user, ps):
        return HttpResponseForbidden('Editing roster fields requires admin role.')
    raw = (request.POST.get('value') or '').strip()

    try:
        if field == 'first_name':
            if not raw:
                return HttpResponseBadRequest('First name cannot be empty.')
            ps.player.first_name = raw
            ps.player.save(update_fields=['first_name', 'updated_at'])
        elif field == 'last_name':
            if not raw:
                return HttpResponseBadRequest('Last name cannot be empty.')
            ps.player.last_name = raw
            ps.player.save(update_fields=['last_name', 'updated_at'])
        elif field == 'date_of_birth':
            if raw:
                try:
                    ps.player.date_of_birth = datetime.strptime(raw, '%Y-%m-%d').date()
                except ValueError:
                    return HttpResponseBadRequest('DOB must be YYYY-MM-DD.')
            else:
                ps.player.date_of_birth = None
            ps.player.save(update_fields=['date_of_birth', 'updated_at'])
        elif field == 'jersey_number':
            if raw:
                try:
                    n = int(raw)
                except ValueError:
                    return HttpResponseBadRequest('Jersey number must be an integer.')
                if n < 0 or n > 999:
                    return HttpResponseBadRequest('Jersey number out of range.')
                ps.jersey_number = n
            else:
                ps.jersey_number = None
            ps.save(update_fields=['jersey_number', 'updated_at'])
        elif field == 'assigned_team':
            if raw:
                try:
                    ts = TeamSeason.objects.select_related('team').get(
                        pk=raw, season=ps.season,
                    )
                except (TeamSeason.DoesNotExist, ValueError):
                    return HttpResponseBadRequest('Unknown team for this season.')
                if ps.division_id and ts.division_id != ps.division_id:
                    return HttpResponseBadRequest('Team is not in the player\'s division.')
                ps.assigned_team = ts
            else:
                ps.assigned_team = None
            ps.save(update_fields=['assigned_team', 'updated_at'])
            # refresh related cache so the template renders the new team name
            ps = PlayerSeason.objects.select_related(
                'player', 'assigned_team__team',
            ).get(pk=ps.pk)
        elif field == 'sub_league':
            ts = ps.assigned_team
            if ts is None:
                return HttpResponseBadRequest(
                    'Assign a team before setting a sub-league.',
                )
            allowed = list((ps.division.league_names or [])) if (
                ps.division and ps.division.has_leagues
            ) else []
            if raw and allowed and raw not in allowed:
                return HttpResponseBadRequest('Sub-league not configured for this division.')
            ts.sub_league = raw
            ts.save(update_fields=['sub_league', 'updated_at'])
    except Exception as exc:  # noqa: BLE001 — surface message to HTMX
        return HttpResponseBadRequest(str(exc))

    return _field_partial(request, ps, field)
