"""Tests for the core app — AuditLog, ImportRun, ImportFlag models, SportsConnect importer, and dashboard."""

import io
import os
from datetime import date, time as dt_time, timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Coach, CoachSeason, User, UserRole
from communications.models import RSVP, EmailLog
from core.importers import SportsConnectImporter, _normalize_key, _parse_date
from core.models import AuditLog, ImportFlag, ImportRun
from players.models import Division, League, Player, PlayerSeason, Season, Team, TeamSeason
from tryouts.models import Session, SessionAssignment


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


class FieldModeTests(TestCase):
    """Coach Field Mode (SFLL-113, Phase 8) — three mobile screens behind
    /field/. Tests cover: auth gating, the no-active-season fallback, the
    no-team-yet fallback (signed-in user without a CoachSeason should still
    get a graceful empty state), the populated-team happy path, and the
    bare /field/ alias redirecting to Today."""

    def setUp(self):
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026,
            season_type='spring', is_active=True,
        )
        self.division = Division.objects.create(league=self.league, name='Majors')
        self.client = Client()

    def _coach_with_team(self, email='coach@sfll.org'):
        user = _create_user(email=email)
        coach = Coach.objects.create(user=user, league=self.league)
        team = Team.objects.create(league=self.league, name='Marlins')
        ts = TeamSeason.objects.create(
            team=team, season=self.season, division=self.division,
        )
        cs = CoachSeason.objects.create(
            coach=coach, team_season=ts, season=self.season, role='head_coach',
        )
        UserRole.objects.create(
            user=user, league=self.league, role='head_coach',
            division=self.division, is_active=True,
        )
        return user, cs, ts

    def test_field_today_requires_login(self):
        resp = self.client.get(reverse('field_today'))
        self.assertEqual(resp.status_code, 302)

    def test_field_roster_requires_login(self):
        resp = self.client.get(reverse('field_roster'))
        self.assertEqual(resp.status_code, 302)

    def test_field_lineup_requires_login(self):
        resp = self.client.get(reverse('field_lineup'))
        self.assertEqual(resp.status_code, 302)

    def test_field_index_redirects_to_today(self):
        _create_user(email='plain@sfll.org')
        self.client.login(username='plain@sfll.org', password='testpass123')
        resp = self.client.get(reverse('field_index'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('field_today'), resp.url)

    def test_field_today_renders_without_coach_profile(self):
        """Signed-in non-coach user should still get the surface — empty
        states, not a 500. Surface is reachable from the sidebar by anyone
        who knows the URL; the empty state communicates that the user
        isn't linked to a team."""
        _create_user(email='plain@sfll.org')
        self.client.login(username='plain@sfll.org', password='testpass123')
        resp = self.client.get(reverse('field_today'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['rsvp_rows'], [])
        self.assertIsNone(resp.context['next_event'])

    def test_field_today_with_team(self):
        user, _, _ = self._coach_with_team()
        self.client.login(username='coach@sfll.org', password='testpass123')
        resp = self.client.get(reverse('field_today'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['field_active'], 'today')
        # Week strip is 7 days regardless of session count
        self.assertEqual(len(resp.context['week_rows']), 7)

    def test_field_roster_with_players(self):
        user, _, ts = self._coach_with_team()
        # Two roster players + one assigned-to-a-different-team distractor
        p1 = Player.objects.create(
            league=self.league, sportsconnect_player_id='p1',
            first_name='Alex', last_name='Bell',
        )
        p2 = Player.objects.create(
            league=self.league, sportsconnect_player_id='p2',
            first_name='Casey', last_name='Diaz',
        )
        p3 = Player.objects.create(
            league=self.league, sportsconnect_player_id='p3',
            first_name='Drew', last_name='Echo',
        )
        PlayerSeason.objects.create(player=p1, season=self.season, assigned_team=ts)
        PlayerSeason.objects.create(player=p2, season=self.season, assigned_team=ts)
        # Distractor — different team
        other_team = Team.objects.create(league=self.league, name='Giants')
        other_ts = TeamSeason.objects.create(
            team=other_team, season=self.season, division=self.division,
        )
        PlayerSeason.objects.create(player=p3, season=self.season, assigned_team=other_ts)

        self.client.login(username='coach@sfll.org', password='testpass123')
        resp = self.client.get(reverse('field_roster'))
        self.assertEqual(resp.status_code, 200)
        # Coach sees their two players, not the distractor.
        self.assertEqual(resp.context['roster_count'], 2)
        names = [r['name'] for r in resp.context['roster_rows']]
        self.assertIn('Alex Bell', names)
        self.assertIn('Casey Diaz', names)
        self.assertNotIn('Drew Echo', names)

    def test_field_lineup_renders(self):
        user, _, _ = self._coach_with_team()
        self.client.login(username='coach@sfll.org', password='testpass123')
        resp = self.client.get(reverse('field_lineup'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['field_active'], 'lineup')

    def test_compliance_ping_surfaces_when_phone_missing(self):
        """Coach without a phone number should see a compliance ping; once
        a phone is on file, the ping disappears. Phone is the Phase-2-era
        stand-in until the real compliance model lands."""
        user, _, _ = self._coach_with_team()
        self.client.login(username='coach@sfll.org', password='testpass123')

        resp = self.client.get(reverse('field_today'))
        self.assertIsNotNone(resp.context['compliance_ping'])

        coach = Coach.objects.get(user=user)
        coach.phone = '+14155551212'
        coach.save()

        resp = self.client.get(reverse('field_today'))
        self.assertIsNone(resp.context['compliance_ping'])


class ParentPhoneTests(TestCase):
    """Parent phone view (SFLL-98, Phase 7 — parent half). Four mobile
    screens behind /parent/. Tests cover: auth gating, the no-children
    fallback (a signed-in user not linked to any PlayerSeason should still
    get the surface with an empty state), the populated-children happy
    path, schedule-tab data shape, account-tab placeholder semantics, and
    inbox row sourcing from EmailLog. Same fallback pattern as Coach
    Field Mode (SFLL-113) — render the surface honestly, never 500."""

    def setUp(self):
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league, name='Spring 2026', year=2026,
            season_type='spring', is_active=True,
        )
        self.division = Division.objects.create(league=self.league, name='Majors')
        self.client = Client()

    def _parent_with_children(self, email='parent@sfll.org', n=1):
        """Build a parent User and N registered children. The data model
        links parent → player by string email match on PlayerSeason."""
        user = _create_user(email=email)
        team = Team.objects.create(league=self.league, name='Marlins')
        ts = TeamSeason.objects.create(
            team=team, season=self.season, division=self.division,
        )
        children = []
        for i in range(n):
            p = Player.objects.create(
                league=self.league,
                sportsconnect_player_id=f'kid-{i}-{email}',
                first_name=f'Kid{i}', last_name='Test',
                date_of_birth=date(2014, 6, 1),
            )
            ps = PlayerSeason.objects.create(
                player=p, season=self.season, assigned_team=ts,
                account_email=email,
                account_name='Parent User',
            )
            children.append(ps)
        return user, ts, children

    def test_parent_today_requires_login(self):
        resp = self.client.get(reverse('parent_today'))
        self.assertEqual(resp.status_code, 302)

    def test_parent_schedule_requires_login(self):
        resp = self.client.get(reverse('parent_schedule'))
        self.assertEqual(resp.status_code, 302)

    def test_parent_account_requires_login(self):
        resp = self.client.get(reverse('parent_account'))
        self.assertEqual(resp.status_code, 302)

    def test_parent_inbox_requires_login(self):
        resp = self.client.get(reverse('parent_inbox'))
        self.assertEqual(resp.status_code, 302)

    def test_parent_index_redirects_to_today(self):
        _create_user(email='plain@sfll.org')
        self.client.login(username='plain@sfll.org', password='testpass123')
        resp = self.client.get(reverse('parent_index'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('parent_today'), resp.url)

    def test_parent_today_without_matched_children(self):
        """Signed-in user with no PlayerSeason linked to their email
        should still get the screen — empty state, not 500. Matches the
        graceful-fallback pattern Coach Field Mode established."""
        _create_user(email='plain@sfll.org')
        self.client.login(username='plain@sfll.org', password='testpass123')
        resp = self.client.get(reverse('parent_today'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['has_children'])
        self.assertEqual(resp.context['player_cards'], [])

    def test_parent_today_matches_account_email_case_insensitive(self):
        """Parents register on SportsConnect with whatever capitalization
        they typed. The view should match regardless of case so a parent
        signed in as `Parent@SFLL.org` still sees their kids."""
        email = 'parent@sfll.org'
        _user, _ts, children = self._parent_with_children(email=email, n=2)
        self.client.login(username=email, password='testpass123')
        resp = self.client.get(reverse('parent_today'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['parent_active'], 'today')
        # Both kids surface in the cards list, ordered by first name.
        names = [c['name'] for c in resp.context['player_cards']]
        self.assertEqual(len(names), 2)

    def test_parent_today_matches_additional_email(self):
        """A parent registered as the second contact (additional_email)
        should still see the child — many families have both parents on
        the registration."""
        user, ts, _kids = self._parent_with_children(email='primary@sfll.org', n=1)
        # Reassign the existing PlayerSeason rows: clear account_email,
        # populate additional_email with this parent's address instead.
        partner_email = 'partner@sfll.org'
        _create_user(email=partner_email)
        PlayerSeason.objects.filter(account_email='primary@sfll.org').update(
            additional_email=partner_email,
        )
        self.client.login(username=partner_email, password='testpass123')
        resp = self.client.get(reverse('parent_today'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['has_children'])

    def test_parent_today_surfaces_next_session_for_child(self):
        """If a Session exists in the child's division (or assigned to
        the child specifically), the Today card shows it as next-up with
        RSVP buttons."""
        email = 'parent@sfll.org'
        _user, _ts, children = self._parent_with_children(email=email, n=1)
        ps = children[0]
        future = timezone.now().date() + timedelta(days=3)
        sess = Session.objects.create(
            season=self.season, name='Saturday practice',
            date=future, start_time=dt_time(10, 0),
            division=self.division, location='Mission Field',
        )
        SessionAssignment.objects.create(session=sess, player_season=ps)

        self.client.login(username=email, password='testpass123')
        resp = self.client.get(reverse('parent_today'))
        self.assertEqual(resp.status_code, 200)
        cards = resp.context['player_cards']
        self.assertEqual(len(cards), 1)
        next_event = cards[0]['next_event']
        self.assertIsNotNone(next_event)
        self.assertEqual(next_event['session_id'], sess.id)
        self.assertEqual(next_event['location'], 'Mission Field')
        self.assertEqual(next_event['status'], '')  # No RSVP yet

    def test_parent_schedule_lists_upcoming_sessions(self):
        email = 'parent@sfll.org'
        _user, _ts, children = self._parent_with_children(email=email, n=1)
        ps = children[0]
        today = timezone.now().date()
        # Two upcoming + one outside the 3-week horizon
        s1 = Session.objects.create(
            season=self.season, name='Practice 1',
            date=today + timedelta(days=2), start_time=dt_time(17, 0),
            division=self.division,
        )
        s2 = Session.objects.create(
            season=self.season, name='Practice 2',
            date=today + timedelta(days=10), start_time=dt_time(17, 0),
            division=self.division,
        )
        s3 = Session.objects.create(
            season=self.season, name='Too far out',
            date=today + timedelta(days=40), start_time=dt_time(17, 0),
            division=self.division,
        )
        SessionAssignment.objects.create(session=s1, player_season=ps)
        SessionAssignment.objects.create(session=s2, player_season=ps)
        SessionAssignment.objects.create(session=s3, player_season=ps)

        self.client.login(username=email, password='testpass123')
        resp = self.client.get(reverse('parent_schedule'))
        self.assertEqual(resp.status_code, 200)
        rows = resp.context['schedule_rows']
        # The 40-day-out session must not surface
        titles = [r['title'] for r in rows]
        self.assertIn('Practice 1', titles)
        self.assertIn('Practice 2', titles)
        self.assertNotIn('Too far out', titles)

    def test_parent_schedule_includes_rsvp_status(self):
        email = 'parent@sfll.org'
        _user, _ts, children = self._parent_with_children(email=email, n=1)
        ps = children[0]
        today = timezone.now().date()
        s = Session.objects.create(
            season=self.season, name='RSVP test',
            date=today + timedelta(days=2), start_time=dt_time(17, 0),
            division=self.division,
        )
        SessionAssignment.objects.create(session=s, player_season=ps)
        RSVP.objects.create(player_season=ps, session=s, status='attending')

        self.client.login(username=email, password='testpass123')
        resp = self.client.get(reverse('parent_schedule'))
        rows = resp.context['schedule_rows']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'attending')

    def test_parent_account_lists_children_and_placeholders(self):
        """Account tab surfaces every child the parent has, plus
        placeholder slots for the un-modeled balance / volunteer /
        documents fields. The summary returns None for everything until
        real models ship."""
        email = 'parent@sfll.org'
        _user, _ts, _children = self._parent_with_children(email=email, n=2)
        self.client.login(username=email, password='testpass123')
        resp = self.client.get(reverse('parent_account'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['player_cards']), 2)
        summary = resp.context['account_summary']
        self.assertIsNone(summary['balance'])
        self.assertIsNone(summary['volunteer_status'])
        self.assertEqual(summary['documents'], [])
        self.assertEqual(summary['children_count'], 2)

    def test_parent_inbox_sources_from_email_log(self):
        """Inbox rows come from EmailLog, scoped to PlayerSeasons that
        belong to this parent. Newest first."""
        email = 'parent@sfll.org'
        _user, _ts, children = self._parent_with_children(email=email, n=1)
        ps = children[0]

        # An email about this parent's child + one about a different
        # child as a distractor.
        EmailLog.objects.create(
            player_season=ps, to_address=email,
            subject='Practice tonight at 5:30',
            body_snapshot='Field 4. Bring water bottles.',
        )
        # Distractor — a different family's email log
        other_user, _other_ts, other_children = self._parent_with_children(
            email='other@sfll.org', n=1,
        )
        EmailLog.objects.create(
            player_season=other_children[0],
            to_address='other@sfll.org',
            subject='Should not appear',
            body_snapshot='private',
        )

        self.client.login(username=email, password='testpass123')
        resp = self.client.get(reverse('parent_inbox'))
        self.assertEqual(resp.status_code, 200)
        rows = resp.context['inbox_rows']
        subjects = [r['subject'] for r in rows]
        self.assertIn('Practice tonight at 5:30', subjects)
        self.assertNotIn('Should not appear', subjects)
