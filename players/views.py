from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from .models import Division, Player, PlayerSeason, Season, Team, TeamSeason


@login_required
def index(request):
    """Player roster — filterable by division, season, search query, family."""
    active_season = Season.objects.filter(is_active=True).first()
    player_seasons = PlayerSeason.objects.select_related(
        'player', 'division', 'assigned_team__team',
    ).filter(season=active_season) if active_season else PlayerSeason.objects.none()

    # SFLL-101 — ⌘K palette deep-links here with ?q= or ?family=, so the
    # palette's "jump to player" / "jump to family" choices land on a
    # filtered roster instead of the unfiltered list.
    search_q = (request.GET.get('q') or '').strip()
    if search_q:
        player_seasons = player_seasons.filter(
            Q(player__first_name__icontains=search_q)
            | Q(player__last_name__icontains=search_q)
        )

    search_family = (request.GET.get('family') or '').strip()
    if search_family:
        player_seasons = player_seasons.filter(account_name=search_family)

    return render(request, 'players/index.html', {
        'player_seasons': player_seasons,
        'season': active_season,
        'divisions': Division.objects.filter(is_active=True),
        'search_q': search_q,
        'search_family': search_family,
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


@login_required
def search(request):
    """HTMX endpoint for the ⌘K command palette (SFLL-101).

    Returns a partial with players matching ``q`` (first or last name) and
    distinct families (PlayerSeason.account_name) grouped with their roster
    count. Scoped to the active season. Capped at 8 of each so the palette
    doesn't render an unbounded list.
    """
    q = (request.GET.get('q') or '').strip()
    active_season = Season.objects.filter(is_active=True).first()

    players: list = []
    families: list = []

    if q and active_season:
        players = list(
            Player.objects
            .filter(seasons__season=active_season)
            .filter(Q(first_name__icontains=q) | Q(last_name__icontains=q))
            .distinct()
            .order_by('last_name', 'first_name')[:8]
        )

        families = list(
            PlayerSeason.objects
            .filter(season=active_season, account_name__icontains=q)
            .exclude(account_name='')
            .values('account_name')
            .annotate(player_count=Count('player', distinct=True))
            .order_by('account_name')[:8]
        )

    return render(request, 'players/_search_results.html', {
        'players': players,
        'families': families,
    })
