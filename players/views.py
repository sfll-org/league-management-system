from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Division, PlayerSeason, Season, TeamSeason


@login_required
def index(request):
    """Player roster — filterable by division and season."""
    active_season = Season.objects.filter(is_active=True).first()
    player_seasons = (
        PlayerSeason.objects.select_related(
            "player",
            "division",
            "assigned_team__team",
        ).filter(season=active_season)
        if active_season
        else PlayerSeason.objects.none()
    )

    return render(
        request,
        "players/index.html",
        {
            "player_seasons": player_seasons,
            "season": active_season,
            "divisions": Division.objects.filter(is_active=True),
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
