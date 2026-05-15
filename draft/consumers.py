import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from core.models import AuditLog
from players.models import PlayerSeason, TeamSeason

from .models import DraftPick, DraftSession

logger = logging.getLogger(__name__)


class DraftConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for the live draft board.

    Each DraftSession gets its own channel group, enabling simultaneous
    drafts across divisions.
    """

    async def connect(self):
        self.draft_session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group = f'draft_{self.draft_session_id}'
        self.user = self.scope.get('user')

        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        # Join the draft room
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        # Send current board state
        state = await self.get_board_state()
        await self.send_json({'type': 'board_state', 'data': state})

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive_json(self, content):
        msg_type = content.get('type')

        if msg_type == 'draft.pick':
            result = await self.handle_pick(content)
            if result.get('success'):
                # Broadcast to all clients in the draft room
                await self.channel_layer.group_send(
                    self.room_group,
                    {
                        'type': 'draft_pick_made',
                        'pick': result['pick'],
                    },
                )
            else:
                await self.send_json({
                    'type': 'error',
                    'message': result.get('error', 'Unknown error'),
                })

        elif msg_type == 'draft.undo':
            result = await self.handle_undo()
            if result.get('success'):
                await self.channel_layer.group_send(
                    self.room_group,
                    {
                        'type': 'draft_pick_undone',
                        'data': result['data'],
                    },
                )
            else:
                await self.send_json({
                    'type': 'error',
                    'message': result.get('error', 'Unknown error'),
                })

    # ------------------------------------------------------------------
    # Broadcast handlers (called by channel_layer.group_send)
    # ------------------------------------------------------------------

    async def draft_pick_made(self, event):
        """Broadcast a completed pick to all connected clients."""
        await self.send_json({
            'type': 'draft.pick_made',
            'pick': event['pick'],
        })

    async def draft_pick_undone(self, event):
        """Broadcast an undo to all connected clients."""
        await self.send_json({
            'type': 'draft.pick_undone',
            'data': event['data'],
        })

    async def draft_started(self, event):
        """Broadcast that the draft has started."""
        await self.send_json({
            'type': 'draft.started',
            'data': event['data'],
        })

    async def draft_completed(self, event):
        """Broadcast that the draft is complete."""
        await self.send_json({
            'type': 'draft.completed',
        })

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    @database_sync_to_async
    def get_board_state(self):
        """Return the full board state for initial client load."""
        try:
            session = DraftSession.objects.select_related(
                'division', 'season',
            ).get(pk=self.draft_session_id)
        except DraftSession.DoesNotExist:
            return {'error': 'Draft session not found.'}

        # Teams in pick order (or alphabetical if no order set)
        team_seasons = list(
            TeamSeason.objects.filter(
                season=session.season,
                division=session.division,
            ).select_related('team', 'drafter__coach__user').order_by('team__name')
        )

        # Determine the ordered list of team IDs
        if session.team_order:
            ordered_ids = session.team_order
            ts_map = {ts.pk: ts for ts in team_seasons}
            ordered_teams = [ts_map[tid] for tid in ordered_ids if tid in ts_map]
        else:
            ordered_teams = team_seasons

        teams = []
        for ts in ordered_teams:
            drafter_name = None
            drafter_user_id = None
            if ts.drafter:
                drafter_name = ts.drafter.coach.user.get_full_name()
                drafter_user_id = ts.drafter.coach.user_id
            teams.append({
                'id': ts.pk,
                'name': ts.team.name,
                'drafter_name': drafter_name,
                'drafter_user_id': drafter_user_id,
            })

        # All picks made so far (including top-4 seeds at round 0)
        picks = list(
            DraftPick.objects.filter(
                draft_session=session,
            ).select_related(
                'player_season__player',
                'team_season__team',
            ).order_by('pick_number')
        )

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

        # Available players (not yet drafted)
        drafted_ps_ids = set(p.player_season_id for p in picks)
        available_ps = list(
            PlayerSeason.objects.filter(
                season=session.season,
                division=session.division,
            ).exclude(
                pk__in=drafted_ps_ids,
            ).select_related('player').order_by(
                'player__last_name', 'player__first_name',
            )
        )

        # Get aggregated eval averages for available players
        from draft.views import _get_aggregated_eval_scores
        eval_scores = _get_aggregated_eval_scores(available_ps, session.season)

        # Get the current user's own coach rankings (if they are a coach)
        my_rankings = {}
        try:
            from accounts.models import CoachSeason
            from evaluations.models import CoachRanking
            coach_season = CoachSeason.objects.get(
                coach__user=self.user,
                season=session.season,
            )
            for cr in CoachRanking.objects.filter(coach_season=coach_season):
                my_rankings[cr.player_season_id] = cr.rank_order
        except Exception:
            pass

        available = []
        for ps in available_ps:
            ev = eval_scores.get(ps.pk, {})
            available.append({
                'id': ps.pk,
                'name': ps.player.full_name,
                'overall_avg': ev.get('overall_avg'),
                'eval_count': ev.get('eval_count', 0),
                'my_rank': my_rankings.get(ps.pk),
            })

        # Determine which team is "on the clock"
        current_team_id = None
        if session.status == 'drafting' and teams:
            current_team_id = self._compute_current_team_id(
                session, [t['id'] for t in teams],
            )

        # Permission flags for the connected user
        is_admin = self._is_draft_admin(session)

        return {
            'session': {
                'id': session.pk,
                'division': session.division.name,
                'status': session.status,
                'current_round': session.current_round,
                'current_pick': session.current_pick,
                'snake_draft': session.snake_draft,
            },
            'teams': teams,
            'picks': picks_data,
            'available': available,
            'current_team_id': current_team_id,
            'is_admin': is_admin,
        }

    def _compute_current_team_id(self, session, team_ids):
        """Given a DraftSession and ordered team IDs, determine who picks next.

        Uses snake draft logic when enabled: odd rounds go forward,
        even rounds go in reverse.
        """
        if not team_ids:
            return None

        num_teams = len(team_ids)
        # current_pick is the overall pick counter (1-indexed, excluding top-4)
        # We need to figure out the index within the current round
        pick_in_round = ((session.current_pick - 1) % num_teams)
        current_round = session.current_round

        if session.snake_draft and current_round % 2 == 0:
            # Even rounds go in reverse
            idx = num_teams - 1 - pick_in_round
        else:
            idx = pick_in_round

        if idx < len(team_ids):
            return team_ids[idx]
        return team_ids[0]

    def _is_draft_admin(self, session):
        """Check whether the connected user is a CTO or Player Agent."""
        if self.user.is_superuser:
            return True
        return self.user.roles.filter(
            is_active=True,
            role__in=['cto', 'ses_manager', 'player_agent'],
        ).exists()

    @database_sync_to_async
    def handle_pick(self, content):
        """Process a draft pick.

        Validates:
        - Draft session is in 'drafting' status
        - It is the correct team's turn
        - The user is the designated drafter for that team (or admin)
        - The player has not already been drafted
        """
        player_season_id = content.get('player_id')
        if not player_season_id:
            return {'error': 'No player specified.'}

        try:
            session = DraftSession.objects.select_related(
                'division', 'season',
            ).get(pk=self.draft_session_id)
        except DraftSession.DoesNotExist:
            return {'error': 'Draft session not found.'}

        if session.status != 'drafting':
            return {'error': 'Draft is not currently active.'}

        # Get teams in order
        team_seasons = list(
            TeamSeason.objects.filter(
                season=session.season,
                division=session.division,
            ).select_related('team', 'drafter__coach__user').order_by('team__name')
        )
        if session.team_order:
            ts_map = {ts.pk: ts for ts in team_seasons}
            ordered_teams = [ts_map[tid] for tid in session.team_order if tid in ts_map]
        else:
            ordered_teams = team_seasons

        team_ids = [ts.pk for ts in ordered_teams]
        current_team_id = self._compute_current_team_id(session, team_ids)

        if not current_team_id:
            return {'error': 'Unable to determine current team.'}

        # Permission check — user must be designated drafter or admin
        current_ts = next((ts for ts in ordered_teams if ts.pk == current_team_id), None)
        is_admin = self._is_draft_admin(session)

        if not is_admin:
            if not current_ts or not current_ts.drafter:
                return {'error': 'No designated drafter for this team.'}
            if current_ts.drafter.coach.user_id != self.user.pk:
                return {'error': 'It is not your turn to pick.'}

        # Validate the player is available
        try:
            player_season = PlayerSeason.objects.select_related('player').get(
                pk=player_season_id,
                season=session.season,
                division=session.division,
            )
        except PlayerSeason.DoesNotExist:
            return {'error': 'Player not found in this division.'}

        if DraftPick.objects.filter(
            draft_session=session,
            player_season=player_season,
        ).exists():
            return {'error': 'Player has already been drafted.'}

        # Determine the actual pick_number for draft picks (top-4 are round 0)
        max_pick = DraftPick.objects.filter(
            draft_session=session,
            is_top_4=False,
        ).count()
        new_pick_number = max_pick + 1

        # Check if player is a coach's child
        is_coaches_child = player_season.coaches_child_of is not None

        # Create the pick
        pick = DraftPick.objects.create(
            draft_session=session,
            team_season_id=current_team_id,
            player_season=player_season,
            round_number=session.current_round,
            pick_number=new_pick_number,
            is_top_4=False,
            is_coaches_child=is_coaches_child,
            picked_by=self.user,
        )

        # Assign the player to the team
        player_season.assigned_team_id = current_team_id
        player_season.save(update_fields=['assigned_team'])

        # Advance the session
        num_teams = len(team_ids)
        picks_in_round = ((session.current_pick - 1) % num_teams) + 1

        if picks_in_round >= num_teams:
            # Round complete — advance to next round
            session.current_round += 1
            session.current_pick = (session.current_round - 1) * num_teams + 1
        else:
            session.current_pick += 1

        session.save(update_fields=['current_round', 'current_pick'])

        # Compute next team on the clock
        next_team_id = self._compute_current_team_id(session, team_ids)

        pick_data = {
            'id': pick.pk,
            'round_number': pick.round_number,
            'pick_number': pick.pick_number,
            'team_id': current_team_id,
            'team_name': current_ts.team.name if current_ts else '',
            'player_id': player_season.pk,
            'player_name': player_season.player.full_name,
            'is_top_4': False,
            'is_coaches_child': is_coaches_child,
            'current_round': session.current_round,
            'current_pick': session.current_pick,
            'next_team_id': next_team_id,
        }

        return {'success': True, 'pick': pick_data}

    @database_sync_to_async
    def handle_undo(self):
        """Undo the last draft pick. CTO/admin only."""
        if not self.user.is_superuser:
            has_admin = self.user.roles.filter(
                is_active=True,
                role__in=['cto'],
            ).exists()
            if not has_admin:
                return {'error': 'Only CTO can undo picks.'}

        try:
            session = DraftSession.objects.get(pk=self.draft_session_id)
        except DraftSession.DoesNotExist:
            return {'error': 'Draft session not found.'}

        if session.status != 'drafting':
            return {'error': 'Draft is not currently active.'}

        # Get the last non-top-4 pick
        last_pick = DraftPick.objects.filter(
            draft_session=session,
            is_top_4=False,
        ).order_by('-pick_number').first()

        if not last_pick:
            return {'error': 'No picks to undo.'}

        undone_data = {
            'player_id': last_pick.player_season_id,
            'player_name': last_pick.player_season.player.full_name,
            'team_id': last_pick.team_season_id,
            'team_name': last_pick.team_season.team.name,
            'pick_number': last_pick.pick_number,
            'round_number': last_pick.round_number,
        }

        # Unassign the player
        ps = last_pick.player_season
        ps.assigned_team = None
        ps.save(update_fields=['assigned_team'])

        # Remove the pick
        last_pick.delete()

        # Decrement session state
        team_seasons = TeamSeason.objects.filter(
            season=session.season,
            division=session.division,
        ).order_by('team__name')
        num_teams = team_seasons.count()

        if session.current_pick > 1:
            session.current_pick -= 1
        # Recalculate current round
        if num_teams > 0:
            session.current_round = ((session.current_pick - 1) // num_teams) + 1
        session.save(update_fields=['current_round', 'current_pick'])

        # Compute which team is now on the clock
        if session.team_order:
            team_ids = session.team_order
        else:
            team_ids = list(team_seasons.values_list('pk', flat=True))

        undone_data['current_round'] = session.current_round
        undone_data['current_pick'] = session.current_pick
        undone_data['next_team_id'] = self._compute_current_team_id(session, team_ids)

        # Audit
        AuditLog.objects.create(
            user=self.user,
            action='undo_pick',
            entity_type='DraftSession',
            entity_id=session.pk,
            details=undone_data,
        )

        return {'success': True, 'data': undone_data}
