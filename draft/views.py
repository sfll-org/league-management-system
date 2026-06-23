import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import CoachSeason, UserRole
from core.models import AuditLog
from evaluations.models import CoachRanking, Evaluation
from players.models import Division, PlayerSeason, Season, Station, TeamSeason

from .models import DraftPick, DraftSession


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _get_active_season():
    return Season.objects.filter(is_active=True).first()


def _get_coach_season(user, season):
    """Get the CoachSeason for this user in the given season."""
    try:
        return CoachSeason.objects.get(coach__user=user, season=season)
    except CoachSeason.DoesNotExist:
        return None
    except CoachSeason.MultipleObjectsReturned:
        return CoachSeason.objects.filter(coach__user=user, season=season).first()


def _is_head_coach(user, season):
    """Check if the user is a head coach for the active season."""
    return CoachSeason.objects.filter(
        coach__user=user,
        season=season,
        role='head_coach',
    ).exists()


def _can_manage_seeding(user, division):
    """Can this user manage pre-draft seeding for a division?"""
    if user.is_superuser:
        return True
    roles = user.roles.filter(is_active=True)
    # CTO and SES Manager can manage all divisions
    if roles.filter(role__in=['cto', 'ses_manager']).exists():
        return True
    # Player Agent can manage their own division
    if roles.filter(role='player_agent', division=division).exists():
        return True
    return False


def _can_view_rankings_aggregated(user, division):
    """Can this user see aggregated coach rankings? (Player Agent+)"""
    if user.is_superuser:
        return True
    roles = user.roles.filter(is_active=True)
    if roles.filter(role__in=['cto', 'ses_manager', 'vp_player_agents']).exists():
        return True
    if roles.filter(role='player_agent', division=division).exists():
        return True
    return False


def _get_aggregated_eval_scores(player_seasons, season):
    """Compute aggregated eval scores for a set of player seasons.

    Returns dict of {player_season_id: {'overall_avg': float, 'eval_count': int, 'station_avgs': {station_name: avg}}}
    Never exposes individual coach scores.
    """
    stations = list(Station.objects.filter(
        league=season.league,
        is_active=True,
    ).order_by('display_order'))

    ps_ids = [ps.pk for ps in player_seasons]
    all_evals = Evaluation.objects.filter(
        player_season_id__in=ps_ids,
    ).select_related('station')

    # Group evals by player_season and station
    eval_map = defaultdict(lambda: defaultdict(list))
    for ev in all_evals:
        eval_map[ev.player_season_id][ev.station_id].append(ev)

    result = {}
    for ps in player_seasons:
        total_score_sum = 0
        total_score_count = 0
        station_avgs = {}
        eval_count = 0

        for station in stations:
            station_evals = eval_map.get(ps.pk, {}).get(station.pk, [])
            eval_count += len(station_evals)
            all_scores = []
            for ev in station_evals:
                for key, val in (ev.scores or {}).items():
                    if isinstance(val, (int, float)):
                        all_scores.append(val)
            if all_scores:
                avg = round(sum(all_scores) / len(all_scores), 1)
                station_avgs[station.name] = avg
                total_score_sum += sum(all_scores)
                total_score_count += len(all_scores)
            else:
                station_avgs[station.name] = None

        overall_avg = round(total_score_sum / total_score_count, 1) if total_score_count else None

        result[ps.pk] = {
            'overall_avg': overall_avg,
            'eval_count': eval_count,
            'station_avgs': station_avgs,
        }

    return result


def _get_aggregated_coach_rankings(player_seasons):
    """Compute aggregated coach ranking data for a set of player seasons.

    Returns dict of {player_season_id: {'times_ranked': int, 'avg_rank': float}}
    Never exposes which coach ranked whom.
    """
    ps_ids = [ps.pk for ps in player_seasons]
    rankings = CoachRanking.objects.filter(player_season_id__in=ps_ids)

    ranking_map = defaultdict(list)
    for r in rankings:
        ranking_map[r.player_season_id].append(r.rank_order)

    result = {}
    for ps in player_seasons:
        ranks = ranking_map.get(ps.pk, [])
        if ranks:
            result[ps.pk] = {
                'times_ranked': len(ranks),
                'avg_rank': round(sum(ranks) / len(ranks), 1),
            }
        else:
            result[ps.pk] = {
                'times_ranked': 0,
                'avg_rank': None,
            }

    return result


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
def draft_home(request):
    """Draft landing page — links to rankings, seeding, and draft board."""
    active_season = _get_active_season()
    if not active_season:
        return render(request, 'draft/draft_home.html', {
            'season': None,
            'draft_sessions': [],
            'is_head_coach': False,
            'coach_season': None,
            'seeding_divisions': [],
        })

    draft_sessions = DraftSession.objects.select_related(
        'division', 'season',
    ).filter(season=active_season)

    coach_season = _get_coach_season(request.user, active_season)
    is_hc = _is_head_coach(request.user, active_season)

    # Determine which divisions this user can manage seeding for
    seeding_divisions = []
    if request.user.is_superuser:
        seeding_divisions = list(Division.objects.filter(
            is_active=True, league=active_season.league,
        ))
    else:
        roles = request.user.roles.filter(is_active=True)
        if roles.filter(role__in=['cto', 'ses_manager']).exists():
            seeding_divisions = list(Division.objects.filter(
                is_active=True, league=active_season.league,
            ))
        else:
            pa_division_ids = roles.filter(role='player_agent').values_list('division_id', flat=True)
            if pa_division_ids:
                seeding_divisions = list(Division.objects.filter(
                    pk__in=pa_division_ids, is_active=True,
                ))

    return render(request, 'draft/draft_home.html', {
        'season': active_season,
        'draft_sessions': draft_sessions,
        'is_head_coach': is_hc,
        'coach_season': coach_season,
        'seeding_divisions': seeding_divisions,
    })


@login_required
def coach_rankings(request):
    """Coach builds their personal ranked wishlist of players."""
    active_season = _get_active_season()
    if not active_season:
        messages.error(request, "No active season configured.")
        return redirect('draft:index')

    coach_season = _get_coach_season(request.user, active_season)
    if not coach_season or coach_season.role != 'head_coach':
        return HttpResponseForbidden("Only head coaches can submit rankings.")

    # Get the division from the coach's team assignment
    division = coach_season.team_season.division

    # All players in the division for the active season
    player_seasons = PlayerSeason.objects.filter(
        season=active_season,
        division=division,
    ).select_related('player', 'coaches_child_of__coach__user').order_by(
        'player__last_name', 'player__first_name',
    )

    # Number of teams in this division
    num_teams = TeamSeason.objects.filter(
        season=active_season,
        division=division,
    ).count()
    max_rankings = 4 * num_teams

    # Load existing rankings for this coach
    existing_rankings = CoachRanking.objects.filter(
        coach_season=coach_season,
    ).order_by('rank_order').select_related('player_season__player')

    ranked_ids = [r.player_season_id for r in existing_rankings]
    ranked_players = list(existing_rankings)

    # Unranked players (not yet in the coach's list)
    unranked = [ps for ps in player_seasons if ps.pk not in ranked_ids]

    return render(request, 'draft/rankings.html', {
        'season': active_season,
        'division': division,
        'coach_season': coach_season,
        'ranked_players': ranked_players,
        'unranked_players': unranked,
        'max_rankings': max_rankings,
        'num_teams': num_teams,
        'total_players': player_seasons.count(),
    })


@login_required
@require_POST
def save_rankings(request):
    """Save coach's ranked player list (POST). Accepts JSON body."""
    active_season = _get_active_season()
    if not active_season:
        return JsonResponse({'error': 'No active season.'}, status=400)

    coach_season = _get_coach_season(request.user, active_season)
    if not coach_season or coach_season.role != 'head_coach':
        return JsonResponse({'error': 'Only head coaches can submit rankings.'}, status=403)

    try:
        data = json.loads(request.body)
        ranked_ids = data.get('ranked_ids', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid request body.'}, status=400)

    if not ranked_ids:
        return JsonResponse({'error': 'No rankings provided.'}, status=400)

    # Validate that all IDs are valid PlayerSeason records in the coach's division
    division = coach_season.team_season.division
    valid_ids = set(
        PlayerSeason.objects.filter(
            season=active_season,
            division=division,
            pk__in=ranked_ids,
        ).values_list('pk', flat=True)
    )

    with transaction.atomic():
        # Delete existing rankings for this coach
        CoachRanking.objects.filter(coach_season=coach_season).delete()

        # Create new rankings
        rankings_to_create = []
        for rank, ps_id in enumerate(ranked_ids, start=1):
            if ps_id in valid_ids:
                rankings_to_create.append(CoachRanking(
                    coach_season=coach_season,
                    player_season_id=ps_id,
                    rank_order=rank,
                ))

        CoachRanking.objects.bulk_create(rankings_to_create)

    return JsonResponse({
        'success': True,
        'count': len(rankings_to_create),
    })


@login_required
def seeding(request, division_id):
    """Pre-draft seeding UI — Player Agent allocates top-4 players per team."""
    division = get_object_or_404(Division, pk=division_id)

    if not _can_manage_seeding(request.user, division):
        return HttpResponseForbidden(
            "You do not have permission to manage seeding for this division."
        )

    active_season = _get_active_season()
    if not active_season:
        messages.error(request, "No active season configured.")
        return redirect('draft:index')

    # Get or create draft session
    draft_session = DraftSession.objects.filter(
        season=active_season,
        division=division,
    ).first()

    is_locked = draft_session and draft_session.status != 'pending'

    # All players in the division
    player_seasons = list(PlayerSeason.objects.filter(
        season=active_season,
        division=division,
    ).select_related(
        'player',
        'coaches_child_of__coach__user',
        'coaches_child_of__team_season__team',
        'assigned_team__team',
    ).order_by('player__last_name', 'player__first_name'))

    # All teams in the division
    team_seasons = list(TeamSeason.objects.filter(
        season=active_season,
        division=division,
    ).select_related('team', 'drafter__coach__user').order_by('team__name'))

    # Get aggregated eval scores
    eval_scores = _get_aggregated_eval_scores(player_seasons, active_season)

    # Get aggregated coach ranking data
    ranking_data = _get_aggregated_coach_rankings(player_seasons)

    # Build player data for the template
    players_data = []
    for ps in player_seasons:
        ev = eval_scores.get(ps.pk, {})
        rk = ranking_data.get(ps.pk, {})
        is_coaches_kid = ps.coaches_child_of is not None
        coaches_kid_team_id = None
        coaches_kid_coach_name = None
        if is_coaches_kid:
            coaches_kid_team_id = ps.coaches_child_of.team_season_id
            coaches_kid_coach_name = ps.coaches_child_of.coach.user.get_full_name()

        players_data.append({
            'id': ps.pk,
            'name': ps.player.full_name,
            'overall_avg': ev.get('overall_avg'),
            'eval_count': ev.get('eval_count', 0),
            'times_ranked': rk.get('times_ranked', 0),
            'avg_rank': rk.get('avg_rank'),
            'is_coaches_kid': is_coaches_kid,
            'coaches_kid_team_id': coaches_kid_team_id,
            'coaches_kid_coach_name': coaches_kid_coach_name,
            'is_top_4': ps.is_top_4,
            'assigned_team_id': ps.assigned_team_id,
        })

    # Sort by overall_avg descending (recommended order)
    players_data.sort(key=lambda p: (p['overall_avg'] is None, -(p['overall_avg'] or 0)))

    # Build team data
    teams_data = []
    for ts in team_seasons:
        drafter_name = None
        if ts.drafter:
            drafter_name = ts.drafter.coach.user.get_full_name()
        teams_data.append({
            'id': ts.pk,
            'name': ts.team.name,
            'drafter_name': drafter_name,
        })

    # Get existing top-4 assignments
    existing_assignments = {}
    if draft_session:
        for pick in DraftPick.objects.filter(
            draft_session=draft_session,
            is_top_4=True,
        ).select_related('player_season', 'team_season'):
            existing_assignments[pick.player_season_id] = pick.team_season_id

    return render(request, 'draft/seeding.html', {
        'season': active_season,
        'division': division,
        'draft_session': draft_session,
        'is_locked': is_locked,
        'players_data': players_data,
        'players_json': json.dumps(players_data),
        'teams_data': teams_data,
        'teams_json': json.dumps(teams_data),
        'existing_assignments': existing_assignments,
        'assignments_json': json.dumps(existing_assignments),
    })


@login_required
@require_POST
def save_seeding(request, division_id):
    """Save pre-draft top-4 assignments (POST). Accepts JSON body."""
    division = get_object_or_404(Division, pk=division_id)

    if not _can_manage_seeding(request.user, division):
        return JsonResponse({'error': 'Permission denied.'}, status=403)

    active_season = _get_active_season()
    if not active_season:
        return JsonResponse({'error': 'No active season.'}, status=400)

    # Get or create draft session
    draft_session, _created = DraftSession.objects.get_or_create(
        season=active_season,
        division=division,
        defaults={'status': 'pending'},
    )

    if draft_session.status != 'pending':
        return JsonResponse({'error': 'Seeding is locked. Cannot modify.'}, status=400)

    try:
        data = json.loads(request.body)
        # assignments: {team_season_id: [player_season_id, ...]}
        assignments = data.get('assignments', {})
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid request body.'}, status=400)

    # Validate
    valid_team_ids = set(
        TeamSeason.objects.filter(
            season=active_season,
            division=division,
        ).values_list('pk', flat=True)
    )
    valid_player_ids = set(
        PlayerSeason.objects.filter(
            season=active_season,
            division=division,
        ).values_list('pk', flat=True)
    )

    with transaction.atomic():
        # Clear existing top-4 picks for this draft session
        DraftPick.objects.filter(draft_session=draft_session, is_top_4=True).delete()

        # Reset is_top_4 and assigned_team for all players in this division
        PlayerSeason.objects.filter(
            season=active_season,
            division=division,
            is_top_4=True,
        ).update(is_top_4=False, draft_slot=None, assigned_team=None)

        pick_number = 1
        total_assigned = 0

        for team_id_str, player_ids in assignments.items():
            team_id = int(team_id_str)
            if team_id not in valid_team_ids:
                continue

            for slot, ps_id in enumerate(player_ids[:4], start=1):
                if ps_id not in valid_player_ids:
                    continue

                # Check if this is a coach's child
                ps = PlayerSeason.objects.get(pk=ps_id)
                is_coaches_child = ps.coaches_child_of is not None

                DraftPick.objects.create(
                    draft_session=draft_session,
                    team_season_id=team_id,
                    player_season_id=ps_id,
                    round_number=0,  # Pre-draft round
                    pick_number=pick_number,
                    is_top_4=True,
                    is_coaches_child=is_coaches_child,
                    picked_by=request.user,
                )

                # Update PlayerSeason
                ps.is_top_4 = True
                ps.draft_slot = slot
                ps.assigned_team_id = team_id
                ps.save(update_fields=['is_top_4', 'draft_slot', 'assigned_team'])

                pick_number += 1
                total_assigned += 1

    return JsonResponse({
        'success': True,
        'total_assigned': total_assigned,
    })


@login_required
@require_POST
def lock_seeding(request, division_id):
    """Lock pre-draft seeding. No more changes allowed after this."""
    division = get_object_or_404(Division, pk=division_id)

    if not _can_manage_seeding(request.user, division):
        return JsonResponse({'error': 'Permission denied.'}, status=403)

    active_season = _get_active_season()
    if not active_season:
        return JsonResponse({'error': 'No active season.'}, status=400)

    draft_session = DraftSession.objects.filter(
        season=active_season,
        division=division,
    ).first()

    if not draft_session:
        return JsonResponse({'error': 'No draft session found.'}, status=404)

    if draft_session.status != 'pending':
        return JsonResponse({'error': 'Seeding is already locked.'}, status=400)

    # Verify there are actual assignments
    top_4_count = DraftPick.objects.filter(
        draft_session=draft_session,
        is_top_4=True,
    ).count()

    if top_4_count == 0:
        return JsonResponse({'error': 'No top-4 assignments to lock.'}, status=400)

    draft_session.status = 'seeding'
    draft_session.save(update_fields=['status'])

    # Create audit log entry
    AuditLog.objects.create(
        user=request.user,
        action='lock_seeding',
        entity_type='DraftSession',
        entity_id=draft_session.pk,
        details={
            'division': division.name,
            'division_id': division.pk,
            'top_4_count': top_4_count,
            'locked_at': timezone.now().isoformat(),
        },
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return JsonResponse({
        'success': True,
        'status': 'seeding',
        'top_4_count': top_4_count,
    })


# ---------------------------------------------------------------------------
# Live Draft Views
# ---------------------------------------------------------------------------

def _can_manage_draft(user, division):
    """Can this user start/control a draft for this division?"""
    if user.is_superuser:
        return True
    roles = user.roles.filter(is_active=True)
    if roles.filter(role__in=['cto', 'ses_manager']).exists():
        return True
    if roles.filter(role='player_agent', division=division).exists():
        return True
    return False


@login_required
def draft_board(request, session_id):
    """Render the live draft board page. Real-time updates via WebSocket."""
    draft_session = get_object_or_404(
        DraftSession.objects.select_related('division', 'season'),
        pk=session_id,
    )
    season = draft_session.season
    division = draft_session.division

    # Teams
    team_seasons = list(
        TeamSeason.objects.filter(
            season=season,
            division=division,
        ).select_related('team', 'drafter__coach__user').order_by('team__name')
    )

    # Apply stored pick order if set
    if draft_session.team_order:
        ts_map = {ts.pk: ts for ts in team_seasons}
        ordered_teams = [ts_map[tid] for tid in draft_session.team_order if tid in ts_map]
    else:
        ordered_teams = team_seasons

    # Picks so far
    picks = list(
        DraftPick.objects.filter(
            draft_session=draft_session,
        ).select_related(
            'player_season__player',
            'team_season__team',
        ).order_by('pick_number')
    )

    drafted_ps_ids = set(p.player_season_id for p in picks)

    # Available players
    available_players = list(
        PlayerSeason.objects.filter(
            season=season,
            division=division,
        ).exclude(
            pk__in=drafted_ps_ids,
        ).select_related('player').order_by(
            'player__last_name', 'player__first_name',
        )
    )

    # Aggregated eval scores for available players
    eval_scores = _get_aggregated_eval_scores(available_players, season)

    # Current user's own rankings (privacy: only their own)
    my_rankings = {}
    coach_season = _get_coach_season(request.user, season)
    if coach_season:
        for cr in CoachRanking.objects.filter(coach_season=coach_season):
            my_rankings[cr.player_season_id] = cr.rank_order

    available_data = []
    for ps in available_players:
        ev = eval_scores.get(ps.pk, {})
        available_data.append({
            'id': ps.pk,
            'name': ps.player.full_name,
            'overall_avg': ev.get('overall_avg'),
            'eval_count': ev.get('eval_count', 0),
            'my_rank': my_rankings.get(ps.pk),
        })

    # Build teams data for JSON
    teams_data = []
    for ts in ordered_teams:
        drafter_name = None
        drafter_user_id = None
        if ts.drafter:
            drafter_name = ts.drafter.coach.user.get_full_name()
            drafter_user_id = ts.drafter.coach.user_id
        teams_data.append({
            'id': ts.pk,
            'name': ts.team.name,
            'drafter_name': drafter_name,
            'drafter_user_id': drafter_user_id,
        })

    picks_data = []
    for pick in picks:
        picks_data.append({
            'id': pick.pk,
            'round_number': pick.round_number,
            'pick_number': pick.pick_number,
            'team_id': pick.team_season_id,
            'team_name': pick.team_season.team.name,
            'player_id': pick.player_season_id,
            'player_name': pick.player_season.player.full_name,
            'is_top_4': pick.is_top_4,
            'is_coaches_child': pick.is_coaches_child,
        })

    # Permission flags
    is_admin = _can_manage_draft(request.user, division)

    # Determine if user is a designated drafter for any team
    drafter_team_id = None
    if coach_season and coach_season.is_drafter:
        for ts in ordered_teams:
            if ts.drafter and ts.drafter.pk == coach_season.pk:
                drafter_team_id = ts.pk
                break

    return render(request, 'draft/draft_board.html', {
        'draft_session': draft_session,
        'season': season,
        'division': division,
        'teams_json': teams_data,
        'picks_json': picks_data,
        'available_json': available_data,
        'is_admin': is_admin,
        'drafter_team_id': drafter_team_id,
        'current_user_id': request.user.pk,
    })


@login_required
def draft_room(request, session_id):
    """Draft Room — iPad-landscape split-pane (SFLL-115 / Phase 10).

    Shares board state with draft_board but reshapes the layout for a tablet
    propped between 2-3 coaches at the table: bigger available-player rows,
    a permanent on-deck queue alongside the pick log, and the on-the-clock
    banner front and center. Reuses the same DraftPick / DraftSession data
    and the same WebSocket for live updates.
    """
    draft_session = get_object_or_404(
        DraftSession.objects.select_related("division", "season"),
        pk=session_id,
    )
    season = draft_session.season
    division = draft_session.division

    team_seasons = list(
        TeamSeason.objects.filter(
            season=season,
            division=division,
        )
        .select_related("team", "drafter__coach__user")
        .order_by("team__name")
    )

    if draft_session.team_order:
        ts_map = {ts.pk: ts for ts in team_seasons}
        ordered_teams = [
            ts_map[tid] for tid in draft_session.team_order if tid in ts_map
        ]
    else:
        ordered_teams = team_seasons

    picks = list(
        DraftPick.objects.filter(
            draft_session=draft_session,
        )
        .select_related(
            "player_season__player",
            "team_season__team",
        )
        .order_by("pick_number")
    )
    drafted_ps_ids = set(p.player_season_id for p in picks)

    available_players = list(
        PlayerSeason.objects.filter(
            season=season,
            division=division,
        )
        .exclude(
            pk__in=drafted_ps_ids,
        )
        .select_related("player")
        .order_by(
            "player__last_name",
            "player__first_name",
        )
    )
    eval_scores = _get_aggregated_eval_scores(available_players, season)

    available_data = []
    for ps in available_players:
        ev = eval_scores.get(ps.pk, {})
        available_data.append({
            "id": ps.pk,
            "name": ps.player.full_name,
            "overall_avg": ev.get("overall_avg"),
            "eval_count": ev.get("eval_count", 0),
        })

    teams_data = []
    for ts in ordered_teams:
        teams_data.append({
            "id": ts.pk,
            "name": ts.team.name,
            "drafter_name": (
                ts.drafter.coach.user.get_full_name() if ts.drafter else None
            ),
        })

    picks_data = []
    for pick in picks:
        picks_data.append({
            "id": pick.pk,
            "round_number": pick.round_number,
            "pick_number": pick.pick_number,
            "team_id": pick.team_season_id,
            "team_name": pick.team_season.team.name,
            "player_id": pick.player_season_id,
            "player_name": pick.player_season.player.full_name,
            "is_top_4": pick.is_top_4,
            "is_coaches_child": pick.is_coaches_child,
        })

    is_admin = _can_manage_draft(request.user, division)

    return render(
        request,
        "draft/draft_room.html",
        {
            "draft_session": draft_session,
            "season": season,
            "division": division,
            "teams_data": teams_data,
            "picks_data": picks_data,
            "available_data": available_data,
            "is_admin": is_admin,
            "current_user_id": request.user.pk,
        },
    )


@login_required
@require_POST
def start_draft(request, session_id):
    """Transition a DraftSession from 'seeding' to 'drafting'. CTO/Player Agent only."""
    draft_session = get_object_or_404(DraftSession, pk=session_id)
    division = draft_session.division

    if not _can_manage_draft(request.user, division):
        return HttpResponseForbidden("You do not have permission to start this draft.")

    if draft_session.status != 'seeding':
        messages.error(request, "Draft can only be started from 'Seeding' status.")
        return redirect('draft:draft_board', session_id=session_id)

    # Determine team pick order — sorted by team name if not already set
    if not draft_session.team_order:
        team_ids = list(
            TeamSeason.objects.filter(
                season=draft_session.season,
                division=division,
            ).order_by('team__name').values_list('pk', flat=True)
        )
        draft_session.team_order = team_ids

    draft_session.status = 'drafting'
    draft_session.started_at = timezone.now()
    draft_session.current_round = 1
    draft_session.current_pick = 1
    draft_session.save(update_fields=[
        'status', 'started_at', 'current_round', 'current_pick', 'team_order',
    ])

    # Audit log
    AuditLog.objects.create(
        user=request.user,
        action='start_draft',
        entity_type='DraftSession',
        entity_id=draft_session.pk,
        details={
            'division': division.name,
            'team_order': draft_session.team_order,
            'started_at': draft_session.started_at.isoformat(),
        },
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    # Broadcast via Channels that draft has started
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'draft_{session_id}',
        {
            'type': 'draft_started',
            'data': {
                'status': 'drafting',
                'current_round': 1,
                'current_pick': 1,
                'team_order': draft_session.team_order,
            },
        },
    )

    messages.success(request, "Draft has started!")
    return redirect('draft:draft_board', session_id=session_id)


@login_required
@require_POST
def undo_pick(request, session_id):
    """Undo the last draft pick. CTO only. Broadcasts via WebSocket."""
    draft_session = get_object_or_404(DraftSession, pk=session_id)

    if not request.user.is_superuser:
        if not request.user.roles.filter(is_active=True, role='cto').exists():
            return JsonResponse({'error': 'Only CTO can undo picks.'}, status=403)

    if draft_session.status != 'drafting':
        return JsonResponse({'error': 'Draft is not currently active.'}, status=400)

    last_pick = DraftPick.objects.filter(
        draft_session=draft_session,
        is_top_4=False,
    ).order_by('-pick_number').first()

    if not last_pick:
        return JsonResponse({'error': 'No picks to undo.'}, status=400)

    undone_data = {
        'player_id': last_pick.player_season_id,
        'player_name': last_pick.player_season.player.full_name,
        'team_id': last_pick.team_season_id,
        'team_name': last_pick.team_season.team.name,
        'pick_number': last_pick.pick_number,
        'round_number': last_pick.round_number,
    }

    # Unassign player
    ps = last_pick.player_season
    ps.assigned_team = None
    ps.save(update_fields=['assigned_team'])

    # Delete the pick
    last_pick.delete()

    # Recalculate session state
    team_seasons = TeamSeason.objects.filter(
        season=draft_session.season,
        division=draft_session.division,
    ).order_by('team__name')
    num_teams = team_seasons.count()

    if draft_session.current_pick > 1:
        draft_session.current_pick -= 1
    if num_teams > 0:
        draft_session.current_round = ((draft_session.current_pick - 1) // num_teams) + 1
    draft_session.save(update_fields=['current_round', 'current_pick'])

    undone_data['current_round'] = draft_session.current_round
    undone_data['current_pick'] = draft_session.current_pick

    # Audit
    AuditLog.objects.create(
        user=request.user,
        action='undo_pick',
        entity_type='DraftSession',
        entity_id=draft_session.pk,
        details=undone_data,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    # Broadcast
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'draft_{session_id}',
        {
            'type': 'draft_pick_undone',
            'data': undone_data,
        },
    )

    return JsonResponse({'success': True, **undone_data})


@login_required
@require_POST
def complete_draft(request, session_id):
    """Mark a draft as completed. CTO/Player Agent only."""
    draft_session = get_object_or_404(DraftSession, pk=session_id)
    division = draft_session.division

    if not _can_manage_draft(request.user, division):
        return HttpResponseForbidden("You do not have permission to complete this draft.")

    if draft_session.status != 'drafting':
        messages.error(request, "Only an active draft can be completed.")
        return redirect('draft:draft_board', session_id=session_id)

    draft_session.status = 'completed'
    draft_session.completed_at = timezone.now()
    draft_session.save(update_fields=['status', 'completed_at'])

    AuditLog.objects.create(
        user=request.user,
        action='complete_draft',
        entity_type='DraftSession',
        entity_id=draft_session.pk,
        details={
            'division': division.name,
            'completed_at': draft_session.completed_at.isoformat(),
            'total_picks': DraftPick.objects.filter(
                draft_session=draft_session,
                is_top_4=False,
            ).count(),
        },
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    # Broadcast completion
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'draft_{session_id}',
        {'type': 'draft_completed'},
    )

    messages.success(request, "Draft has been completed!")
    return redirect('draft:post_draft_rosters', session_id=session_id)


@login_required
def post_draft_rosters(request, session_id):
    """Show final team rosters after draft completion."""
    draft_session = get_object_or_404(
        DraftSession.objects.select_related('division', 'season'),
        pk=session_id,
    )
    season = draft_session.season
    division = draft_session.division

    # All teams in this division
    team_seasons = list(
        TeamSeason.objects.filter(
            season=season,
            division=division,
        ).select_related('team').order_by('team__name')
    )

    # All picks for this session, grouped by team
    picks = DraftPick.objects.filter(
        draft_session=draft_session,
    ).select_related(
        'player_season__player',
        'team_season__team',
    ).order_by('pick_number')

    teams_rosters = {}
    for ts in team_seasons:
        teams_rosters[ts.pk] = {
            'team': ts,
            'team_name': ts.team.name,
            'top_4': [],
            'drafted': [],
        }

    for pick in picks:
        entry = {
            'player_name': pick.player_season.player.full_name,
            'round_number': pick.round_number,
            'pick_number': pick.pick_number,
            'is_coaches_child': pick.is_coaches_child,
        }
        if pick.is_top_4:
            teams_rosters[pick.team_season_id]['top_4'].append(entry)
        else:
            teams_rosters[pick.team_season_id]['drafted'].append(entry)

    is_admin = _can_manage_draft(request.user, division)

    return render(request, 'draft/post_draft_rosters.html', {
        'draft_session': draft_session,
        'season': season,
        'division': division,
        'teams_rosters': teams_rosters,
        'is_admin': is_admin,
    })
