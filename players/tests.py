"""Tests for the players app — League, Season, Division, Station, Player, PlayerSeason, Team, TeamSeason."""

from datetime import date

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from players.models import (
    Division, League, Player, PlayerSeason, Season, Station, Team, TeamSeason,
)


def _create_league():
    return League.objects.create(
        name='San Francisco Little League',
        short_name='SFLL',
    )


def _create_user(email='test@sfll.org', password='testpass123'):
    return User.objects.create_user(
        username=email, email=email,
        first_name='Test', last_name='User',
        password=password,
    )


class LeagueModelTests(TestCase):
    def test_str_returns_short_name(self):
        league = _create_league()
        self.assertEqual(str(league), 'SFLL')

    def test_defaults(self):
        league = _create_league()
        self.assertEqual(league.timezone, 'America/New_York')
        self.assertEqual(league.sportsconnect_sync_interval_minutes, 60)


class SeasonModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()

    def test_str_format(self):
        season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026, season_type='spring',
        )
        self.assertEqual(str(season), 'Spring 2026 (2026)')

    def test_default_flags(self):
        season = Season.objects.create(
            league=self.league, name='Fall 2025', year=2025, season_type='fall',
        )
        self.assertFalse(season.is_active)
        self.assertFalse(season.registration_open)
        self.assertFalse(season.draft_complete)

    def test_ordering(self):
        Season.objects.create(league=self.league, name='S1', year=2025, season_type='spring')
        Season.objects.create(league=self.league, name='S2', year=2026, season_type='spring')
        seasons = list(Season.objects.all())
        self.assertEqual(seasons[0].year, 2026)


class DivisionModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()

    def test_str(self):
        div = Division.objects.create(league=self.league, name='Majors')
        self.assertEqual(str(div), 'Majors')

    def test_ordering_by_display_order(self):
        Division.objects.create(league=self.league, name='AA', display_order=2)
        Division.objects.create(league=self.league, name='Majors', display_order=0)
        Division.objects.create(league=self.league, name='AAA', display_order=1)
        divs = list(Division.objects.all())
        self.assertEqual([d.name for d in divs], ['Majors', 'AAA', 'AA'])

    def test_has_leagues_default(self):
        div = Division.objects.create(league=self.league, name='AA')
        self.assertFalse(div.has_leagues)
        self.assertEqual(div.league_names, [])


class StationModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()

    def test_str(self):
        station = Station.objects.create(
            league=self.league, name='Hitting', display_order=0,
        )
        self.assertEqual(str(station), 'Hitting (SFLL)')

    def test_eval_fields_default(self):
        station = Station.objects.create(
            league=self.league, name='Fielding',
        )
        self.assertEqual(station.eval_fields, [])

    def test_eval_fields_json(self):
        fields = [{'key': 'power', 'label': 'Power', 'type': 'int', 'min': 1, 'max': 10}]
        station = Station.objects.create(
            league=self.league, name='Hitting', eval_fields=fields,
        )
        self.assertEqual(station.eval_fields[0]['key'], 'power')


class PlayerModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()

    def test_str(self):
        p = Player.objects.create(
            league=self.league,
            sportsconnect_player_id='SC-001',
            first_name='Jayden',
            last_name='Rodriguez',
        )
        self.assertEqual(str(p), 'Jayden Rodriguez')

    def test_full_name_property(self):
        p = Player.objects.create(
            league=self.league,
            sportsconnect_player_id='SC-002',
            first_name='Aiden',
            last_name='Martinez',
        )
        self.assertEqual(p.full_name, 'Aiden Martinez')

    def test_sportsconnect_player_id_unique(self):
        Player.objects.create(
            league=self.league, sportsconnect_player_id='SC-DUP',
            first_name='A', last_name='B',
        )
        with self.assertRaises(Exception):
            Player.objects.create(
                league=self.league, sportsconnect_player_id='SC-DUP',
                first_name='C', last_name='D',
            )

    def test_ordering(self):
        Player.objects.create(
            league=self.league, sportsconnect_player_id='SC-Z',
            first_name='Zoe', last_name='Anderson',
        )
        Player.objects.create(
            league=self.league, sportsconnect_player_id='SC-A',
            first_name='Aaron', last_name='Adams',
        )
        players = list(Player.objects.all())
        self.assertEqual(players[0].last_name, 'Adams')


class PlayerSeasonModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026, season_type='spring',
            is_active=True,
        )
        self.division = Division.objects.create(league=self.league, name='Majors')
        self.player = Player.objects.create(
            league=self.league, sportsconnect_player_id='SC-100',
            first_name='Test', last_name='Player',
        )

    def test_create(self):
        ps = PlayerSeason.objects.create(
            player=self.player, season=self.season, division=self.division,
        )
        self.assertEqual(ps.status, 'registered')
        self.assertFalse(ps.is_protected)
        self.assertFalse(ps.is_top_4)

    def test_str(self):
        ps = PlayerSeason.objects.create(
            player=self.player, season=self.season, division=self.division,
        )
        self.assertIn('Test Player', str(ps))
        self.assertIn('Spring 2026', str(ps))

    def test_unique_together_player_season(self):
        PlayerSeason.objects.create(
            player=self.player, season=self.season, division=self.division,
        )
        with self.assertRaises(Exception):
            PlayerSeason.objects.create(
                player=self.player, season=self.season, division=self.division,
            )

    def test_rsvp_token_auto_generated(self):
        ps = PlayerSeason.objects.create(
            player=self.player, season=self.season,
        )
        self.assertIsNotNone(ps.rsvp_token)

    def test_checkin_token_auto_generated(self):
        ps = PlayerSeason.objects.create(
            player=self.player, season=self.season,
        )
        self.assertIsNotNone(ps.checkin_token)


class TeamModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026, season_type='spring',
        )
        self.division = Division.objects.create(league=self.league, name='Majors')

    def test_team_str(self):
        team = Team.objects.create(league=self.league, name='Marlins')
        self.assertEqual(str(team), 'Marlins')

    def test_team_season_str(self):
        team = Team.objects.create(league=self.league, name='Dolphins')
        ts = TeamSeason.objects.create(
            team=team, season=self.season, division=self.division,
        )
        result = str(ts)
        self.assertIn('Dolphins', result)
        self.assertIn('Majors', result)

    def test_team_season_with_sub_league(self):
        team = Team.objects.create(league=self.league, name='Dolphins')
        ts = TeamSeason.objects.create(
            team=team, season=self.season, division=self.division,
            sub_league='American',
        )
        self.assertIn('American', str(ts))

    def test_team_season_unique_together(self):
        team = Team.objects.create(league=self.league, name='Marlins')
        TeamSeason.objects.create(
            team=team, season=self.season, division=self.division,
        )
        with self.assertRaises(Exception):
            TeamSeason.objects.create(
                team=team, season=self.season, division=self.division,
            )


class PlayerViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = _create_user()
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026, season_type='spring',
            is_active=True,
        )

    def test_index_requires_login(self):
        resp = self.client.get(reverse('players:index'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_index_authenticated(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:index'))
        self.assertEqual(resp.status_code, 200)

    def test_teams_requires_login(self):
        resp = self.client.get(reverse('players:teams'))
        self.assertEqual(resp.status_code, 302)

    def test_teams_authenticated(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:teams'))
        self.assertEqual(resp.status_code, 200)


class PrintSurfaceTests(TestCase):
    """Print preview / dugout roster card (SFLL-114, Phase 9)."""

    def setUp(self):
        self.client = Client()
        self.user = _create_user()
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026, season_type='spring',
            is_active=True,
        )
        self.division = Division.objects.create(
            league=self.league, name='Majors', display_order=1,
        )
        self.team = Team.objects.create(league=self.league, name='Dolphins')
        self.team_season = TeamSeason.objects.create(
            team=self.team, season=self.season, division=self.division,
            sub_league='American',
        )

    def test_print_index_requires_login(self):
        resp = self.client.get(reverse('players:print_index'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_print_index_lists_team(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:print_index'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Dolphins')
        self.assertContains(resp, 'Print card')

    def test_print_index_empty_when_no_active_season(self):
        Season.objects.filter(pk=self.season.pk).update(is_active=False)
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:print_index'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No active season')

    def test_dugout_card_requires_login(self):
        resp = self.client.get(
            reverse('players:print_dugout_card', args=[self.team_season.pk])
        )
        self.assertEqual(resp.status_code, 302)

    def test_dugout_card_renders_team_strip(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:print_dugout_card', args=[self.team_season.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Dolphins')
        self.assertContains(resp, 'Majors')
        self.assertContains(resp, 'American')

    def test_dugout_card_404_for_unknown_team(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:print_dugout_card', args=[99999])
        )
        self.assertEqual(resp.status_code, 404)

    def test_dugout_card_includes_roster_emergency_contacts(self):
        player = Player.objects.create(
            league=self.league,
            sportsconnect_player_id='SCP-1',
            first_name='Mia',
            last_name='Nguyen',
        )
        PlayerSeason.objects.create(
            player=player,
            season=self.season,
            division=self.division,
            assigned_team=self.team_season,
            account_name='Linh Nguyen',
            account_email='linh@example.com',
            additional_email='backup@example.com',
        )
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:print_dugout_card', args=[self.team_season.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Mia Nguyen')
        self.assertContains(resp, 'Linh Nguyen')
        self.assertContains(resp, 'linh@example.com')
        self.assertContains(resp, 'backup@example.com')

    def test_dugout_card_auto_print_default(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:print_dugout_card', args=[self.team_season.pk])
        )
        # The auto-print path emits an addEventListener('load') handler.
        self.assertContains(resp, "addEventListener('load'")

    def test_dugout_card_auto_print_suppressed_with_query(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:print_dugout_card', args=[self.team_season.pk])
            + '?print=0'
        )
        # The manual reprint button still calls window.print(), so anchor
        # on the auto-firing addEventListener('load') call that only the
        # auto path emits.
        self.assertNotContains(resp, "addEventListener('load'")


class PlayerDetailViewTests(TestCase):
    """SFLL-94 Phase 4 — Player Detail page + HTMX inline-edit endpoints."""

    def setUp(self):
        self.client = Client()
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026, season_type='spring',
            is_active=True,
        )
        self.division = Division.objects.create(
            league=self.league, name='Majors', has_leagues=True,
            league_names=['American', 'National'],
        )
        self.team = Team.objects.create(league=self.league, name='Marlins')
        self.team_season = TeamSeason.objects.create(
            team=self.team, season=self.season, division=self.division,
            sub_league='American',
        )
        self.player = Player.objects.create(
            league=self.league, sportsconnect_player_id='SC-PD-1',
            first_name='Jayden', last_name='Rodriguez',
            date_of_birth=date(2014, 7, 4),
        )
        self.ps = PlayerSeason.objects.create(
            player=self.player, season=self.season, division=self.division,
            assigned_team=self.team_season, jersey_number=12,
        )
        self.viewer = _create_user(email='viewer@sfll.org')
        self.admin = _create_user(email='admin@sfll.org')
        self.admin.is_staff = True
        self.admin.save()
        # Give admin a global CTO role — needed for the Evals tab, which
        # requires an actual UserRole, not just is_staff (mirrors the
        # evaluations app's privacy model).
        from accounts.models import UserRole
        UserRole.objects.create(
            user=self.admin, league=self.league, role='cto', is_active=True,
        )

    # ---------------- page rendering ----------------

    def test_detail_requires_login(self):
        resp = self.client.get(reverse('players:detail', args=[self.ps.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_detail_renders(self):
        self.client.login(username='viewer@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:detail', args=[self.ps.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Jayden Rodriguez')
        # Tab nav present
        self.assertContains(resp, 'Overview')
        self.assertContains(resp, 'Season')
        self.assertContains(resp, 'Evals')

    def test_detail_overview_shows_inline_fields(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:detail', args=[self.ps.pk]))
        self.assertContains(resp, 'id="field-first_name"')
        self.assertContains(resp, 'id="field-jersey_number"')
        self.assertContains(resp, 'id="field-assigned_team"')
        # Admin sees clickable trigger
        self.assertContains(resp, 'editable-trigger')

    def test_detail_non_editor_sees_static(self):
        self.client.login(username='viewer@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:detail', args=[self.ps.pk]))
        self.assertNotContains(resp, 'editable-trigger')
        # Static read-mode wrapper instead
        self.assertContains(resp, 'detail-row__static')

    def test_detail_season_tab(self):
        self.client.login(username='viewer@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:detail', args=[self.ps.pk]) + '?tab=season',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'SES attendance')

    def test_detail_evals_tab_for_non_privileged_is_locked(self):
        self.client.login(username='viewer@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:detail', args=[self.ps.pk]) + '?tab=evals',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'aggregated and access-controlled')

    def test_detail_evals_tab_for_admin_shows_grid(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:detail', args=[self.ps.pk]) + '?tab=evals',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Composite score')

    # ---------------- HTMX inline-edit endpoints ----------------

    def test_field_edit_requires_admin(self):
        self.client.login(username='viewer@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:detail_field_edit', args=[self.ps.pk, 'first_name']),
        )
        self.assertEqual(resp.status_code, 403)

    def test_field_edit_admin_gets_form(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:detail_field_edit', args=[self.ps.pk, 'first_name']),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="value"')
        self.assertContains(resp, 'value="Jayden"')

    def test_field_edit_unknown_field_rejected(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:detail_field_edit', args=[self.ps.pk, 'middle_name']),
        )
        self.assertEqual(resp.status_code, 400)

    def test_field_save_first_name(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'first_name']),
            {'value': 'Jayde'},
        )
        self.assertEqual(resp.status_code, 200)
        self.player.refresh_from_db()
        self.assertEqual(self.player.first_name, 'Jayde')

    def test_field_save_first_name_empty_rejected(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'first_name']),
            {'value': ''},
        )
        self.assertEqual(resp.status_code, 400)

    def test_field_save_date_of_birth(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'date_of_birth']),
            {'value': '2014-08-15'},
        )
        self.assertEqual(resp.status_code, 200)
        self.player.refresh_from_db()
        self.assertEqual(self.player.date_of_birth, date(2014, 8, 15))

    def test_field_save_date_of_birth_invalid(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'date_of_birth']),
            {'value': '08/15/2014'},
        )
        self.assertEqual(resp.status_code, 400)

    def test_field_save_jersey_number(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'jersey_number']),
            {'value': '7'},
        )
        self.assertEqual(resp.status_code, 200)
        self.ps.refresh_from_db()
        self.assertEqual(self.ps.jersey_number, 7)

    def test_field_save_jersey_number_clear(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'jersey_number']),
            {'value': ''},
        )
        self.assertEqual(resp.status_code, 200)
        self.ps.refresh_from_db()
        self.assertIsNone(self.ps.jersey_number)

    def test_field_save_jersey_number_zero(self):
        """Jersey number 0 must save, display as #0, and not render as dash."""
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'jersey_number']),
            {'value': '0'},
        )
        self.assertEqual(resp.status_code, 200)
        self.ps.refresh_from_db()
        self.assertEqual(self.ps.jersey_number, 0)
        self.assertContains(resp, '#0')

    def test_roster_jersey_number_zero_renders(self):
        """Jersey #0 must appear as #0 in the roster, not as a dash."""
        self.ps.jersey_number = 0
        self.ps.save()
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:index'))
        self.assertContains(resp, '#0')
        self.assertNotContains(resp, 'col-num">—')

    def test_field_read_jersey_number_zero_renders(self):
        """Read-mode partial for jersey_number=0 must show #0, not a dash."""
        self.ps.jersey_number = 0
        self.ps.save()
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:detail_field', args=[self.ps.pk, 'jersey_number'])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '#0')

    def test_field_save_jersey_number_out_of_range(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'jersey_number']),
            {'value': '1000'},
        )
        self.assertEqual(resp.status_code, 400)

    def test_field_save_assigned_team(self):
        other_team = Team.objects.create(league=self.league, name='Giants')
        other_ts = TeamSeason.objects.create(
            team=other_team, season=self.season, division=self.division,
        )
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'assigned_team']),
            {'value': str(other_ts.pk)},
        )
        self.assertEqual(resp.status_code, 200)
        self.ps.refresh_from_db()
        self.assertEqual(self.ps.assigned_team_id, other_ts.pk)

    def test_field_save_assigned_team_clear(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'assigned_team']),
            {'value': ''},
        )
        self.assertEqual(resp.status_code, 200)
        self.ps.refresh_from_db()
        self.assertIsNone(self.ps.assigned_team)

    def test_field_save_assigned_team_rejects_wrong_division(self):
        # A same-season team from a different division must be rejected.
        # Without the division guard, PlayerSeason.division and
        # assigned_team.division would diverge, corrupting roster/draft views.
        other_division = Division.objects.create(
            league=self.league, name='AAA', display_order=1,
        )
        other_team = Team.objects.create(league=self.league, name='Cubs')
        other_ts = TeamSeason.objects.create(
            team=other_team, season=self.season, division=other_division,
        )
        original_team_id = self.ps.assigned_team_id
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'assigned_team']),
            {'value': str(other_ts.pk)},
        )
        self.assertEqual(resp.status_code, 400)
        self.ps.refresh_from_db()
        self.assertEqual(self.ps.assigned_team_id, original_team_id)

    def test_field_save_sub_league(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'sub_league']),
            {'value': 'National'},
        )
        self.assertEqual(resp.status_code, 200)
        self.team_season.refresh_from_db()
        self.assertEqual(self.team_season.sub_league, 'National')

    def test_field_save_sub_league_rejects_unknown_value(self):
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'sub_league']),
            {'value': 'Federal'},
        )
        self.assertEqual(resp.status_code, 400)

    def test_field_save_sub_league_without_team(self):
        # Clear team first
        self.ps.assigned_team = None
        self.ps.save(update_fields=['assigned_team'])
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'sub_league']),
            {'value': 'National'},
        )
        self.assertEqual(resp.status_code, 400)

    def test_field_save_requires_admin(self):
        self.client.login(username='viewer@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'first_name']),
            {'value': 'Hax'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_field_cancel_returns_read_partial(self):
        # GET on detail_field returns read-mode — used to cancel edits.
        self.client.login(username='viewer@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:detail_field', args=[self.ps.pk, 'first_name']),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Jayden')

    def test_field_save_player_agent_same_division_allowed(self):
        """Player Agent scoped to the player's division can edit roster fields."""
        from accounts.models import UserRole
        agent = _create_user(email='majors_agent@sfll.org')
        UserRole.objects.create(
            user=agent, league=self.league, role='player_agent',
            division=self.division, is_active=True,
        )
        self.client.login(username='majors_agent@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'jersey_number']),
            {'value': '42'},
        )
        self.assertEqual(resp.status_code, 200)
        self.ps.refresh_from_db()
        self.assertEqual(self.ps.jersey_number, 42)

    def test_field_save_player_agent_wrong_division_denied(self):
        """Player Agent from a different division is denied with 403."""
        from accounts.models import UserRole
        other_division = Division.objects.create(
            league=self.league, name='AAA', display_order=1,
        )
        agent = _create_user(email='aaa_agent@sfll.org')
        UserRole.objects.create(
            user=agent, league=self.league, role='player_agent',
            division=other_division, is_active=True,
        )
        self.client.login(username='aaa_agent@sfll.org', password='testpass123')
        original_jersey = self.ps.jersey_number
        resp = self.client.post(
            reverse('players:detail_field_save', args=[self.ps.pk, 'jersey_number']),
            {'value': '99'},
        )
        self.assertEqual(resp.status_code, 403)
        self.ps.refresh_from_db()
        self.assertEqual(self.ps.jersey_number, original_jersey)


class RosterFiltersTests(TestCase):
    """The roster page also got rebuilt off Tailwind in this phase; verify the
    new filter chips don't 500."""

    def setUp(self):
        self.client = Client()
        self.user = _create_user(email='roster@sfll.org')
        league = _create_league()
        season = Season.objects.create(
            league=league, name='Spring 2026', year=2026, season_type='spring',
            is_active=True,
        )
        self.division = Division.objects.create(league=league, name='Majors')
        Player.objects.create(
            league=league, sportsconnect_player_id='RT-1',
            first_name='A', last_name='Alpha',
        ).seasons.create(season=season, division=self.division, is_top_4=True)
        Player.objects.create(
            league=league, sportsconnect_player_id='RT-2',
            first_name='B', last_name='Beta',
        ).seasons.create(season=season, division=self.division)

    def test_roster_top4_filter(self):
        self.client.login(username='roster@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:index') + '?view=top4')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Alpha')
        self.assertNotContains(resp, 'Beta')

    def test_roster_unassigned_filter(self):
        self.client.login(username='roster@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:index') + '?view=unassigned')
        self.assertEqual(resp.status_code, 200)
        # Both are unassigned (no assigned_team set above)
        self.assertContains(resp, 'Alpha')
        self.assertContains(resp, 'Beta')

    def test_roster_division_filter(self):
        self.client.login(username='roster@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:index') + f'?division={self.division.pk}',
        )
        self.assertEqual(resp.status_code, 200)

    def test_roster_search(self):
        self.client.login(username='roster@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:index') + '?q=Alpha')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Alpha')
