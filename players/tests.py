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
