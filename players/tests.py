"""Tests for the players app — League, Season, Division, Station, Player, PlayerSeason, Team, TeamSeason, plus Family Detail (SFLL-95)."""

from datetime import date

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User, UserRole
from communications.models import EmailLog
from players.models import (
    Division, League, Player, PlayerSeason, Season, Station, Team, TeamSeason,
)
from players.views import encode_family_key


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


class DugoutCardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = _create_user()
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026, season_type='spring',
            is_active=True,
        )
        self.division = Division.objects.create(league=self.league, name='Majors')
        self.team = Team.objects.create(league=self.league, name='Marlins')
        self.team_season = TeamSeason.objects.create(
            team=self.team, season=self.season, division=self.division,
        )
        self.player = Player.objects.create(
            league=self.league, sportsconnect_player_id='sc-1',
            first_name='Ada', last_name='Lovelace',
        )
        self.ps = PlayerSeason.objects.create(
            player=self.player, season=self.season, division=self.division,
            assigned_team=self.team_season, account_name='Augusta Lovelace',
        )

    def test_dugout_card_requires_login(self):
        resp = self.client.get(
            reverse('players:dugout_card', args=[self.team_season.pk]),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_dugout_card_renders_for_valid_team(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:dugout_card', args=[self.team_season.pk]),
        )
        self.assertEqual(resp.status_code, 200)
        # Team strip header, roster row, guardian, schedule heading,
        # and the window.print() Print button are all on the card.
        self.assertContains(resp, 'Marlins')
        self.assertContains(resp, 'Ada Lovelace')
        self.assertContains(resp, 'Augusta Lovelace')
        self.assertContains(resp, 'Next 5 games')
        self.assertContains(resp, 'window.print()')

    def test_dugout_card_404_for_missing_team(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:dugout_card', args=[9999]),
        )
        self.assertEqual(resp.status_code, 404)

    def test_dugout_card_renders_empty_roster(self):
        empty_team = Team.objects.create(league=self.league, name='Penguins')
        empty_ts = TeamSeason.objects.create(
            team=empty_team, season=self.season, division=self.division,
        )
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:dugout_card', args=[empty_ts.pk]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No players assigned')


# ---------------------------------------------------------------------------
# SFLL-95 — Family Detail (Phase 4)
# ---------------------------------------------------------------------------

FAMILY_EMAIL = 'rodriguez.family@example.com'
OTHER_FAMILY_EMAIL = 'other@example.com'


class FamilyDetailTests(TestCase):
    """Family Detail page: groups PlayerSeasons by account_email and surfaces
    players, contacts, balance shell, volunteer shell, and comms history."""

    def setUp(self):
        self.client = Client()
        self.user = _create_user()
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026, season_type='spring',
            is_active=True,
        )
        self.division = Division.objects.create(league=self.league, name='Majors')

        self.player1 = Player.objects.create(
            league=self.league, sportsconnect_player_id='SC-FAM-1',
            first_name='Jayden', last_name='Rodriguez',
        )
        self.player2 = Player.objects.create(
            league=self.league, sportsconnect_player_id='SC-FAM-2',
            first_name='Alex', last_name='Rodriguez',
        )
        self.ps1 = PlayerSeason.objects.create(
            player=self.player1, season=self.season, division=self.division,
            account_name='Maria Rodriguez',
            account_email=FAMILY_EMAIL,
            additional_email='papa@example.com',
        )
        self.ps2 = PlayerSeason.objects.create(
            player=self.player2, season=self.season, division=self.division,
            account_name='Maria Rodriguez',
            account_email=FAMILY_EMAIL,
        )
        # An unrelated player on a different account.
        other_player = Player.objects.create(
            league=self.league, sportsconnect_player_id='SC-OTHER',
            first_name='Other', last_name='Kid',
        )
        PlayerSeason.objects.create(
            player=other_player, season=self.season, division=self.division,
            account_name='Other Parent', account_email=OTHER_FAMILY_EMAIL,
        )

        self.family_key = encode_family_key(FAMILY_EMAIL)

    # ----- index -----

    def test_family_index_requires_login(self):
        resp = self.client.get(reverse('players:family_index'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_family_index_lists_families(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:family_index'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Maria Rodriguez')
        self.assertContains(resp, FAMILY_EMAIL)
        self.assertContains(resp, 'Other Parent')

    def test_family_index_no_active_season(self):
        self.season.is_active = False
        self.season.save()
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:family_index'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No active season')

    # ----- detail -----

    def test_family_detail_requires_login(self):
        resp = self.client.get(
            reverse('players:family_detail', args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_family_detail_renders(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:family_detail', args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        # Header pulls account name + sibling count.
        self.assertContains(resp, 'Maria Rodriguez')
        self.assertContains(resp, '2 players')
        # Both siblings appear.
        self.assertContains(resp, 'Jayden Rodriguez')
        self.assertContains(resp, 'Alex Rodriguez')
        # Other family isn't accidentally pulled in.
        self.assertNotContains(resp, 'Other Kid')
        # Contacts grid shows primary + secondary; emergency is a placeholder.
        self.assertContains(resp, 'Primary parent')
        self.assertContains(resp, 'Secondary contact')
        self.assertContains(resp, 'Emergency contact')
        self.assertContains(resp, 'papa@example.com')
        # Volunteer shell and division context.
        self.assertContains(resp, 'Volunteer obligations')
        self.assertContains(resp, 'Majors')
        # Comms shell renders even with no email logs.
        self.assertContains(resp, 'Recent communications')

    def test_family_detail_404_for_unknown_family(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        bogus = encode_family_key('nobody@example.com')
        resp = self.client.get(
            reverse('players:family_detail', args=[bogus]),
        )
        self.assertEqual(resp.status_code, 404)

    def test_family_detail_404_for_malformed_key(self):
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:family_detail', args=['not-a-valid-key!!!']),
        )
        self.assertEqual(resp.status_code, 404)

    def test_family_detail_404_when_no_active_season(self):
        self.season.is_active = False
        self.season.save()
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:family_detail', args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 404)

    def test_family_detail_includes_comms_history(self):
        EmailLog.objects.create(
            player_season=self.ps1,
            to_address=FAMILY_EMAIL,
            subject='SES reminder for Jayden',
            body_snapshot='You have an SES session tomorrow.',
        )
        EmailLog.objects.create(
            player_season=self.ps2,
            to_address=FAMILY_EMAIL,
            subject='SES reminder for Alex',
            body_snapshot='You have an SES session tomorrow.',
        )
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:family_detail', args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'SES reminder for Jayden')
        self.assertContains(resp, 'SES reminder for Alex')

    # ----- treasurer + balance gating -----

    def test_balance_section_hidden_for_regular_user(self):
        # Plain logged-in user (no admin / treasurer role) sees no balance.
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:family_detail', args=[self.family_key]),
        )
        self.assertNotContains(resp, '>Balance<')
        self.assertNotContains(resp, 'Treasurer view')

    def test_treasurer_sees_balance_in_readonly_mode(self):
        UserRole.objects.create(
            user=self.user, league=self.league, role='treasurer',
        )
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:family_detail', args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Balance')
        self.assertContains(resp, 'Treasurer view')
        self.assertContains(resp, 'read-only')

    def test_admin_sees_balance_without_readonly_badge(self):
        UserRole.objects.create(
            user=self.user, league=self.league, role='cto',
        )
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:family_detail', args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Balance')
        self.assertNotContains(resp, 'Treasurer view')

    def test_treasurer_plus_admin_loses_readonly_badge(self):
        # Multi-role: someone with both treasurer and admin caps shouldn't be
        # locked into the read-only view.
        UserRole.objects.create(
            user=self.user, league=self.league, role='treasurer',
        )
        UserRole.objects.create(
            user=self.user, league=self.league, role='president',
        )
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:family_detail', args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Balance')
        self.assertNotContains(resp, 'Treasurer view')

    def test_balance_hidden_for_role_in_other_league(self):
        # A treasurer or admin role on a *different* League must not grant
        # visibility into this family's Balance section.
        other_league = League.objects.create(
            name='Oakland Little League', short_name='OLL',
        )
        UserRole.objects.create(
            user=self.user, league=other_league, role='treasurer',
        )
        UserRole.objects.create(
            user=self.user, league=other_league, role='president',
        )
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:family_detail', args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Balance')
        self.assertNotContains(resp, 'Treasurer view')
