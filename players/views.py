from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from accounts.models import CoachSeason
from tryouts.models import Session

from .models import Division, Player, PlayerSeason, Season, Team, TeamSeason


@login_required
def index(request):
    """Player roster — filterable by division and season."""
    active_season = Season.objects.filter(is_active=True).first()
    player_seasons = PlayerSeason.objects.select_related(
        'player', 'division', 'assigned_team__team',
    ).filter(season=active_season) if active_season else PlayerSeason.objects.none()

    return render(request, 'players/index.html', {
        'player_seasons': player_seasons,
        'season': active_season,
        'divisions': Division.objects.filter(is_active=True),
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
