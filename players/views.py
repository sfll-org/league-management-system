from django.contrib.auth.decorators import login_required
from django.shortcuts import render

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
