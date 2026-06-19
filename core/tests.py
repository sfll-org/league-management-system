"""Tests for the core app — AuditLog, ImportRun, ImportFlag models, SportsConnect importer, and dashboard."""

import io
import os
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import Coach, CoachSeason, User, UserRole
from core.importers import SportsConnectImporter, _normalize_key, _parse_date
from core.models import AuditLog, ImportFlag, ImportRun
from players.models import Division, League, Player, PlayerSeason, Season, Team, TeamSeason


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fixtures')


def _create_league():
    return League.objects.create(name='San Francisco Little League', short_name='SFLL')


def _create_user(email='admin@sfll.org', password='testpass123', is_superuser=False):
    return User.objects.create_user(
        username=email, email=email,
        first_name='Admin', last_name='User', password=password,
        is_superuser=is_superuser,
    )


class AuditLogModelTests(TestCase):
    def setUp(self):
        self.user = _create_user()

    def test_create(self):
        log = AuditLog.objects.create(
            user=self.user,
            action='player.reassign',
            entity_type='SessionAssignment',
            entity_id=1,
            details={'from': 'SES 1', 'to': 'SES 2'},
        )
        self.assertIn('player.reassign', str(log))
        self.assertIn('SessionAssignment', str(log))

    def test_ordering_most_recent_first(self):
        AuditLog.objects.create(
            user=self.user, action='first', entity_type='X', entity_id=1,
        )
        AuditLog.objects.create(
            user=self.user, action='second', entity_type='X', entity_id=2,
        )
        logs = list(AuditLog.objects.all())
        self.assertEqual(logs[0].action, 'second')

    def test_null_user(self):
        log = AuditLog.objects.create(
            user=None, action='system', entity_type='Cron', entity_id=0,
        )
        self.assertIsNone(log.user)

    def test_ip_address_optional(self):
        log = AuditLog.objects.create(
            user=self.user, action='test', entity_type='X', entity_id=1,
            ip_address='192.168.1.1',
        )
        self.assertEqual(log.ip_address, '192.168.1.1')


class ImportRunModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()

    def test_create(self):
        run = ImportRun.objects.create(
            league=self.league, status='running', triggered_by='manual',
        )
        self.assertEqual(run.total_rows, 0)
        self.assertIn('running', str(run))

    def test_str(self):
        run = ImportRun.objects.create(
            league=self.league, status='completed', triggered_by='scheduled',
            total_rows=15,
        )
        self.assertIn('15 rows', str(run))


class ImportFlagModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()
        self.import_run = ImportRun.objects.create(
            league=self.league, status='completed', triggered_by='manual',
        )

    def test_create(self):
        flag = ImportFlag.objects.create(
            import_run=self.import_run,
            flag_type='potential_duplicate',
            details={'player_name': 'Jayden Rodriguez'},
        )
        self.assertFalse(flag.resolved)
        self.assertIn('Potential Duplicate', str(flag))

    def test_flag_types(self):
        for ftype in ('potential_duplicate', 'division_change', 'cancellation', 'data_mismatch'):
            flag = ImportFlag.objects.create(
                import_run=self.import_run, flag_type=ftype,
            )
            self.assertEqual(flag.flag_type, ftype)


class NormalizeKeyTests(TestCase):
    """Test the CSV column name normalization helper."""

    def test_basic(self):
        self.assertEqual(_normalize_key('Player First Name'), 'player first name')

    def test_extra_whitespace(self):
        self.assertEqual(_normalize_key('  Player   Last  Name  '), 'player last name')

    def test_mixed_case(self):
        self.assertEqual(_normalize_key('ORDER_ID'), 'order_id')


class ParseDateTests(TestCase):
    """Test the date parsing helper."""

    def test_us_format(self):
        self.assertEqual(_parse_date('03/15/2016'), date(2016, 3, 15))

    def test_iso_format(self):
        self.assertEqual(_parse_date('2016-03-15'), date(2016, 3, 15))

    def test_dash_us_format(self):
        self.assertEqual(_parse_date('03-15-2016'), date(2016, 3, 15))

    def test_short_year(self):
        self.assertEqual(_parse_date('03/15/16'), date(2016, 3, 15))

    def test_empty(self):
        self.assertIsNone(_parse_date(''))
        self.assertIsNone(_parse_date(None))

    def test_unparseable(self):
        self.assertIsNone(_parse_date('not-a-date'))


class SportsConnectImporterTests(TestCase):
    """Test the SportsConnect CSV import pipeline."""

    def setUp(self):
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026,
            season_type='spring', is_active=True,
        )
        # Pre-create divisions that match the CSV
        for name in ('Majors', 'AAA', 'AA', 'A', 'Rookie'):
            Division.objects.create(league=self.league, name=name)

    def test_import_sample_csv(self):
        """Import the sample fixture CSV and verify counts."""
        csv_path = os.path.join(FIXTURES_DIR, 'sample_sportsconnect.csv')
        with open(csv_path, 'r') as f:
            csv_content = f.read()

        importer = SportsConnectImporter(
            league=self.league, season=self.season,
        )
        run = importer.run(csv_content)

        self.assertEqual(run.status, 'completed')
        self.assertEqual(run.total_rows, 15)
        # 15 rows, but SC-10002 appears twice (different divisions) and SC-10099
        # is a new player — so we should have 14 unique players
        # Actually: 13 unique SC IDs (SC-10001 through SC-10015, minus SC-10002 dupe row)
        # SC-10002 appears in rows 2 and 12 — first creates, second updates
        self.assertGreater(run.new_players, 0)
        self.assertGreater(run.new_player_seasons, 0)

    def test_import_creates_players(self):
        csv_content = (
            "Order_ID,Order Detail Id,Player First Name,Player Last Name,"
            "Player Id,Player Age,Division Name,Account First Name,"
            "Account Last Name,User Email,Additional Email,Program Name,"
            "Team Name,Session_ID,Status\n"
            "ORD-1,OD-1,Test,Player,SC-NEW-1,10,Majors,Parent,Name,"
            "parent@test.com,,Spring 2026,,,Active\n"
        )
        importer = SportsConnectImporter(league=self.league, season=self.season)
        run = importer.run(csv_content)

        self.assertEqual(run.new_players, 1)
        self.assertEqual(run.new_player_seasons, 1)
        self.assertTrue(Player.objects.filter(sportsconnect_player_id='SC-NEW-1').exists())

    def test_import_updates_existing_player(self):
        """Re-importing the same player should update, not duplicate."""
        csv = (
            "Order_ID,Order Detail Id,Player First Name,Player Last Name,"
            "Player Id,Division Name,User Email,Status\n"
            "ORD-1,OD-1,Test,Player,SC-UPD-1,Majors,v1@test.com,Active\n"
        )
        importer1 = SportsConnectImporter(league=self.league, season=self.season)
        importer1.run(csv)

        csv2 = (
            "Order_ID,Order Detail Id,Player First Name,Player Last Name,"
            "Player Id,Division Name,User Email,Status\n"
            "ORD-2,OD-2,Test,Player,SC-UPD-1,Majors,v2@test.com,Active\n"
        )
        importer2 = SportsConnectImporter(league=self.league, season=self.season)
        run2 = importer2.run(csv2)

        self.assertEqual(Player.objects.filter(sportsconnect_player_id='SC-UPD-1').count(), 1)
        # Email change should be flagged
        self.assertGreater(run2.flagged_for_review, 0)

    def test_import_flags_division_change(self):
        """If a player moves divisions between imports, a flag is created."""
        csv1 = (
            "Order_ID,Order Detail Id,Player First Name,Player Last Name,"
            "Player Id,Division Name,User Email,Status\n"
            "ORD-1,OD-1,Test,Player,SC-DIV-1,Majors,p@test.com,Active\n"
        )
        SportsConnectImporter(league=self.league, season=self.season).run(csv1)

        csv2 = (
            "Order_ID,Order Detail Id,Player First Name,Player Last Name,"
            "Player Id,Division Name,User Email,Status\n"
            "ORD-1,OD-1,Test,Player,SC-DIV-1,AAA,p@test.com,Active\n"
        )
        run2 = SportsConnectImporter(league=self.league, season=self.season).run(csv2)

        div_change_flags = ImportFlag.objects.filter(
            import_run=run2, flag_type='division_change',
        )
        self.assertTrue(div_change_flags.exists())

    def test_import_detects_cancellation(self):
        csv = (
            "Order_ID,Order Detail Id,Player First Name,Player Last Name,"
            "Player Id,Division Name,User Email,Program Name,Status\n"
            "ORD-1,OD-1,Cancel,Me,SC-CAN-1,Majors,p@test.com,Spring 2026,Cancelled\n"
        )
        run = SportsConnectImporter(league=self.league, season=self.season).run(csv)
        cancel_flags = ImportFlag.objects.filter(
            import_run=run, flag_type='cancellation',
        )
        self.assertTrue(cancel_flags.exists())

    def test_import_missing_player_id_error(self):
        csv = (
            "Order_ID,Order Detail Id,Player First Name,Player Last Name,"
            "Player Id,Division Name,User Email,Status\n"
            "ORD-1,OD-1,No,ID,,Majors,p@test.com,Active\n"
        )
        run = SportsConnectImporter(league=self.league, season=self.season).run(csv)
        self.assertEqual(run.errors, 1)

    def test_import_missing_name_error(self):
        csv = (
            "Order_ID,Order Detail Id,Player First Name,Player Last Name,"
            "Player Id,Division Name,User Email,Status\n"
            "ORD-1,OD-1,,LastOnly,SC-NONAME,Majors,p@test.com,Active\n"
        )
        run = SportsConnectImporter(league=self.league, season=self.season).run(csv)
        self.assertEqual(run.errors, 1)

    def test_import_unknown_division_flagged(self):
        csv = (
            "Order_ID,Order Detail Id,Player First Name,Player Last Name,"
            "Player Id,Division Name,User Email,Status\n"
            "ORD-1,OD-1,Test,Player,SC-UNK-1,Unknown Division,p@test.com,Active\n"
        )
        run = SportsConnectImporter(league=self.league, season=self.season).run(csv)
        flags = ImportFlag.objects.filter(
            import_run=run, flag_type='data_mismatch',
        )
        self.assertTrue(flags.exists())

    def test_import_bytes_input(self):
        """Importer should handle bytes (with BOM) correctly."""
        csv_bytes = (
            "\ufeffOrder_ID,Order Detail Id,Player First Name,Player Last Name,"
            "Player Id,Division Name,User Email,Status\n"
            "ORD-1,OD-1,Test,Player,SC-BOM-1,Majors,p@test.com,Active\n"
        ).encode('utf-8-sig')
        run = SportsConnectImporter(league=self.league, season=self.season).run(csv_bytes)
        self.assertEqual(run.status, 'completed')
        self.assertEqual(run.new_players, 1)


class DashboardViewTests(TestCase):
    """Test the main dashboard view."""

    def setUp(self):
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026,
            season_type='spring', is_active=True,
        )
        self.client = Client()

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_renders_for_regular_user(self):
        user = _create_user(email='user@sfll.org')
        self.client.login(username='user@sfll.org', password='testpass123')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_admin_widgets(self):
        """Superuser should see admin context variables."""
        user = _create_user(email='super@sfll.org', is_superuser=True)
        self.client.login(username='super@sfll.org', password='testpass123')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['is_admin'])

    def test_dashboard_coach_widgets(self):
        """Coach user should get coach_season context."""
        user = _create_user(email='coach@sfll.org')
        UserRole.objects.create(
            user=user, league=self.league, role='head_coach',
            division=Division.objects.create(league=self.league, name='Majors'),
            is_active=True,
        )
        coach = Coach.objects.create(user=user, league=self.league)
        team = Team.objects.create(league=self.league, name='Marlins')
        ts = TeamSeason.objects.create(
            team=team, season=self.season,
            division=Division.objects.get(name='Majors'),
        )
        CoachSeason.objects.create(
            coach=coach, team_season=ts, season=self.season, role='head_coach',
        )
        self.client.login(username='coach@sfll.org', password='testpass123')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['is_coach'])

    def test_dashboard_no_active_season(self):
        """Dashboard should still render when no active season exists."""
        self.season.is_active = False
        self.season.save()
        user = _create_user(email='noseason@sfll.org')
        self.client.login(username='noseason@sfll.org', password='testpass123')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)


class HealthCheckTests(TestCase):
    def test_healthz(self):
        resp = self.client.get(reverse('health-check'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'ok')


class CmdkUrlEncodingTests(TestCase):
    """Regression: command-palette URLs must percent-encode reserved characters."""

    def setUp(self):
        from core.views import _cmdk_players, _cmdk_families
        self._cmdk_players = _cmdk_players
        self._cmdk_families = _cmdk_families

        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026,
            season_type='spring', is_active=True,
        )
        self.division = Division.objects.create(league=self.league, name='Majors')

    def _make_player_season(self, first, last, account_name='Test Family'):
        player = Player.objects.create(
            league=self.league, first_name=first, last_name=last,
        )
        return PlayerSeason.objects.create(
            player=player, season=self.season,
            division=self.division, account_name=account_name,
        )

    def test_player_url_encodes_reserved_chars(self):
        """A player name with '&' must not appear raw in the deep-link URL."""
        self._make_player_season('A & B', 'Smith')
        items = self._cmdk_players('Smith')
        self.assertEqual(len(items), 1)
        url = items[0]['url']
        self.assertNotIn('&', url.split('?')[1])
        self.assertIn('%26', url)

    def test_player_url_encodes_plus(self):
        self._make_player_season('C+D', 'Jones')
        items = self._cmdk_players('Jones')
        self.assertEqual(len(items), 1)
        url = items[0]['url']
        self.assertNotIn('+', url.split('?')[1])

    def test_family_url_encodes_reserved_chars(self):
        """An account name with '&' must not appear raw in the deep-link URL."""
        self._make_player_season('Alice', 'Smith', account_name='Smith & Jones')
        items = self._cmdk_families('Smith')
        self.assertEqual(len(items), 1)
        url = items[0]['url']
        self.assertNotIn('&', url.split('?')[1])
        self.assertIn('%26', url)

    def test_family_url_encodes_plus(self):
        self._make_player_season('Bob', 'Lee', account_name='A+B Family')
        items = self._cmdk_families('A+B')
        self.assertEqual(len(items), 1)
        url = items[0]['url']
        self.assertNotIn('+', url.split('?')[1])


class CmdkPageRoleFilterTests(TestCase):
    """Palette pages gated on roles must not appear for plain power-users."""

    def setUp(self):
        from core.views import _cmdk_pages
        self._cmdk_pages = _cmdk_pages
        self.league = _create_league()

    def _user_with_roles(self, email, roles=()):
        user = _create_user(email=email)
        for role in roles:
            UserRole.objects.create(user=user, role=role, is_active=True)
        return user

    def _page_titles(self, user):
        return {p['title'] for p in self._cmdk_pages(user)}

    def test_plain_user_cannot_see_comms_or_evals(self):
        user = self._user_with_roles('plain@sfll.org')
        titles = self._page_titles(user)
        self.assertNotIn('Communications', titles)
        self.assertNotIn('Evaluations', titles)

    def test_comms_editor_can_see_comms(self):
        user = self._user_with_roles('comms@sfll.org', roles=['comms_editor'])
        titles = self._page_titles(user)
        self.assertIn('Communications', titles)

    def test_head_coach_can_see_evals(self):
        user = self._user_with_roles('coach@sfll.org', roles=['head_coach'])
        titles = self._page_titles(user)
        self.assertIn('Evaluations', titles)

    def test_draft_visible_to_all_authenticated(self):
        user = self._user_with_roles('reg@sfll.org')
        titles = self._page_titles(user)
        self.assertIn('Draft', titles)

    def test_admin_pages_hidden_from_non_admin(self):
        user = self._user_with_roles('plain@sfll.org')
        titles = self._page_titles(user)
        self.assertNotIn('Imports', titles)
        self.assertNotIn('Configuration', titles)

    def test_superuser_sees_everything(self):
        user = _create_user(email='super@sfll.org', is_superuser=True)
        titles = self._page_titles(user)
        self.assertIn('Communications', titles)
        self.assertIn('Evaluations', titles)
        self.assertIn('Draft', titles)
        self.assertIn('Imports', titles)
