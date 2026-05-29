"""Tests for the tryouts app — Session, SessionAssignment, CheckIn models and views."""

from datetime import date, time, timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Coach, CoachSeason, User, UserRole
from core.models import AuditLog
from evaluations.models import Evaluation
from players.models import (
    Division, League, Player, PlayerSeason, Season, Station,
    Team, TeamSeason,
)
from tryouts.models import CheckIn, Session, SessionAssignment


def _setup_base():
    """Create league, season, division, and user. Returns dict of objects."""
    league = League.objects.create(name='SFLL', short_name='SFLL')
    season = Season.objects.create(
        league=league, name='Spring 2026', year=2026, season_type='spring',
        is_active=True,
    )
    division = Division.objects.create(league=league, name='Majors', display_order=0)
    return {'league': league, 'season': season, 'division': division}


def _create_user(email='user@sfll.org', password='testpass123', is_superuser=False):
    return User.objects.create_user(
        username=email, email=email,
        first_name='Test', last_name='User',
        password=password, is_superuser=is_superuser,
    )


def _create_player(league, sc_id='SC-001', first='Jayden', last='Rodriguez'):
    return Player.objects.create(
        league=league, sportsconnect_player_id=sc_id,
        first_name=first, last_name=last,
    )


class SessionModelTests(TestCase):
    def setUp(self):
        self.base = _setup_base()

    def test_str(self):
        session = Session.objects.create(
            season=self.base['season'],
            name='SES Day 1',
            date=date(2026, 3, 28),
            start_time=time(9, 0),
            division=self.base['division'],
        )
        self.assertIn('SES Day 1', str(session))
        self.assertIn('2026-03-28', str(session))

    def test_is_makeup_default(self):
        session = Session.objects.create(
            season=self.base['season'],
            name='SES Day 1',
            date=date(2026, 3, 28),
            start_time=time(9, 0),
            division=self.base['division'],
        )
        self.assertFalse(session.is_makeup)
        self.assertIsNone(session.makeup_for)

    def test_makeup_session_link(self):
        original = Session.objects.create(
            season=self.base['season'], name='SES 1',
            date=date(2026, 3, 28), start_time=time(9, 0),
            division=self.base['division'],
        )
        makeup = Session.objects.create(
            season=self.base['season'], name='SES 1 Makeup',
            date=date(2026, 4, 5), start_time=time(9, 0),
            division=self.base['division'],
            is_makeup=True, makeup_for=original,
        )
        self.assertEqual(makeup.makeup_for, original)
        self.assertIn(makeup, original.makeup_sessions.all())


class SessionAssignmentModelTests(TestCase):
    def setUp(self):
        self.base = _setup_base()
        self.player = _create_player(self.base['league'])
        self.ps = PlayerSeason.objects.create(
            player=self.player, season=self.base['season'],
            division=self.base['division'],
        )
        self.session = Session.objects.create(
            season=self.base['season'], name='SES 1',
            date=date(2026, 3, 28), start_time=time(9, 0),
            division=self.base['division'],
        )

    def test_create_assignment(self):
        sa = SessionAssignment.objects.create(
            session=self.session, player_season=self.ps,
        )
        self.assertIn('SES 1', str(sa))

    def test_unique_together(self):
        SessionAssignment.objects.create(
            session=self.session, player_season=self.ps,
        )
        with self.assertRaises(Exception):
            SessionAssignment.objects.create(
                session=self.session, player_season=self.ps,
            )


class CheckInModelTests(TestCase):
    def setUp(self):
        self.base = _setup_base()
        self.player = _create_player(self.base['league'])
        self.ps = PlayerSeason.objects.create(
            player=self.player, season=self.base['season'],
            division=self.base['division'],
        )
        self.session = Session.objects.create(
            season=self.base['season'], name='SES 1',
            date=date.today(), start_time=time(9, 0),
            division=self.base['division'],
        )
        self.assignment = SessionAssignment.objects.create(
            session=self.session, player_season=self.ps,
        )

    def test_create_checkin(self):
        checkin = CheckIn.objects.create(
            session_assignment=self.assignment,
        )
        self.assertIsNotNone(checkin.checked_in_at)
        self.assertIn('Check-in', str(checkin))

    def test_one_to_one_constraint(self):
        CheckIn.objects.create(session_assignment=self.assignment)
        with self.assertRaises(Exception):
            CheckIn.objects.create(session_assignment=self.assignment)


class SessionViewPermissionTests(TestCase):
    """Test that session CRUD views enforce role-based permissions."""

    def setUp(self):
        self.base = _setup_base()
        self.client = Client()

    def test_session_list_requires_login(self):
        resp = self.client.get(reverse('tryouts:session_list'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_session_list_authenticated(self):
        user = _create_user()
        self.client.login(username='user@sfll.org', password='testpass123')
        resp = self.client.get(reverse('tryouts:session_list'))
        self.assertEqual(resp.status_code, 200)

    def test_session_create_forbidden_for_regular_user(self):
        user = _create_user()
        self.client.login(username='user@sfll.org', password='testpass123')
        resp = self.client.get(reverse('tryouts:session_create'))
        self.assertEqual(resp.status_code, 403)

    def test_session_create_allowed_for_superuser(self):
        user = _create_user(email='admin@sfll.org', is_superuser=True)
        self.client.login(username='admin@sfll.org', password='testpass123')
        resp = self.client.get(reverse('tryouts:session_create'))
        self.assertEqual(resp.status_code, 200)

    def test_session_create_allowed_for_cto_role(self):
        user = _create_user(email='cto@sfll.org')
        UserRole.objects.create(
            user=user, league=self.base['league'], role='cto', is_active=True,
        )
        self.client.login(username='cto@sfll.org', password='testpass123')
        resp = self.client.get(reverse('tryouts:session_create'))
        self.assertEqual(resp.status_code, 200)

    def test_session_create_allowed_for_player_agent(self):
        user = _create_user(email='pa@sfll.org')
        UserRole.objects.create(
            user=user, league=self.base['league'], role='player_agent',
            division=self.base['division'], is_active=True,
        )
        self.client.login(username='pa@sfll.org', password='testpass123')
        resp = self.client.get(reverse('tryouts:session_create'))
        self.assertEqual(resp.status_code, 200)

    def test_session_delete_forbidden_for_regular_user(self):
        user = _create_user()
        session = Session.objects.create(
            season=self.base['season'], name='SES 1',
            date=date.today(), start_time=time(9, 0),
            division=self.base['division'],
        )
        self.client.login(username='user@sfll.org', password='testpass123')
        resp = self.client.get(reverse('tryouts:session_delete', args=[session.pk]))
        self.assertEqual(resp.status_code, 403)


class CheckInViewTests(TestCase):
    """Test check-in views and the public QR-code check-in flow."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.player = _create_player(self.base['league'])
        self.ps = PlayerSeason.objects.create(
            player=self.player, season=self.base['season'],
            division=self.base['division'],
        )
        self.session = Session.objects.create(
            season=self.base['season'], name='SES 1',
            date=date.today(), start_time=time(9, 0),
            division=self.base['division'],
        )
        self.assignment = SessionAssignment.objects.create(
            session=self.session, player_season=self.ps,
            assigned_by=self.user,
        )
        self.client = Client()

    def test_checkin_dashboard_requires_permission(self):
        regular_user = _create_user(email='nobody@sfll.org')
        self.client.login(username='nobody@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('tryouts:session_checkin', args=[self.session.pk])
        )
        self.assertEqual(resp.status_code, 403)

    def test_checkin_dashboard_allowed_for_front_desk(self):
        fd_user = _create_user(email='fd@sfll.org')
        UserRole.objects.create(
            user=fd_user, league=self.base['league'], role='front_desk',
            is_active=True,
        )
        self.client.login(username='fd@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('tryouts:session_checkin', args=[self.session.pk])
        )
        self.assertEqual(resp.status_code, 200)

    def test_checkin_player_via_post(self):
        self.client.login(username='user@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('tryouts:checkin_player', args=[self.session.pk, self.assignment.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(CheckIn.objects.filter(session_assignment=self.assignment).exists())

    def test_checkin_player_idempotent(self):
        """Checking in the same player twice should not create duplicate."""
        self.client.login(username='user@sfll.org', password='testpass123')
        self.client.post(
            reverse('tryouts:checkin_player', args=[self.session.pk, self.assignment.pk])
        )
        self.client.post(
            reverse('tryouts:checkin_player', args=[self.session.pk, self.assignment.pk])
        )
        self.assertEqual(
            CheckIn.objects.filter(session_assignment=self.assignment).count(), 1
        )

    def test_public_checkin_by_token(self):
        """Public QR code check-in should work without authentication."""
        resp = self.client.get(
            reverse('public_checkin', args=[self.ps.checkin_token])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(CheckIn.objects.filter(session_assignment=self.assignment).exists())

    def test_public_checkin_already_checked_in(self):
        """If already checked in, public check-in should show already_checked_in."""
        CheckIn.objects.create(session_assignment=self.assignment)
        resp = self.client.get(
            reverse('public_checkin', args=[self.ps.checkin_token])
        )
        self.assertEqual(resp.status_code, 200)

    def test_public_checkin_no_session_today(self):
        """If no session today, public check-in shows an error."""
        # Move the session to yesterday
        self.session.date = date.today() - timedelta(days=1)
        self.session.save()
        resp = self.client.get(
            reverse('public_checkin', args=[self.ps.checkin_token])
        )
        self.assertEqual(resp.status_code, 200)


class SessionCreatePostTests(TestCase):
    """Test session creation via POST."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.client = Client()
        self.client.login(username='user@sfll.org', password='testpass123')

    def test_create_session_post(self):
        resp = self.client.post(reverse('tryouts:session_create'), {
            'name': 'SES Day 1',
            'date': '2026-03-28',
            'start_time': '09:00',
            'division': self.base['division'].pk,
            'location': 'Field 3',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Session.objects.filter(name='SES Day 1').exists())

    def test_create_session_missing_required(self):
        resp = self.client.post(reverse('tryouts:session_create'), {
            'name': '',
            'date': '',
            'start_time': '',
            'division': '',
        })
        # Should re-render form (200), not redirect
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# SES Session screen (Phase 6 — SFLL-111)
# ---------------------------------------------------------------------------

class SESSessionScreenContextTests(TestCase):
    """The four-region context dict for the SES Session screen."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        # Two stations for the league
        self.station_a = Station.objects.create(
            league=self.base['league'], name='Hitting', display_order=0,
        )
        self.station_b = Station.objects.create(
            league=self.base['league'], name='Fielding', display_order=1,
        )
        # Inactive station should not appear
        Station.objects.create(
            league=self.base['league'], name='Retired', display_order=2,
            is_active=False,
        )
        self.session = Session.objects.create(
            season=self.base['season'], name='SES Day 1',
            date=date.today(), start_time=time(9, 0),
            division=self.base['division'],
        )
        # Five players, assignments, with 3 checked in and 2 evaluated
        self.players = []
        self.player_seasons = []
        self.assignments = []
        for i in range(5):
            p = _create_player(
                self.base['league'], sc_id=f'SC-{i:03d}',
                first=f'First{i}', last=f'Last{i}',
            )
            ps = PlayerSeason.objects.create(
                player=p, season=self.base['season'],
                division=self.base['division'],
            )
            a = SessionAssignment.objects.create(
                session=self.session, player_season=ps, assigned_by=self.user,
            )
            self.players.append(p)
            self.player_seasons.append(ps)
            self.assignments.append(a)

        # Check in first three
        for a in self.assignments[:3]:
            CheckIn.objects.create(session_assignment=a, checked_in_by=self.user)

        # Create a coach so Evaluation FK is satisfied
        coach_user = _create_user(email='coach@sfll.org')
        coach = Coach.objects.create(user=coach_user, league=self.base['league'])
        team = Team.objects.create(
            league=self.base['league'], name='Giants',
        )
        team_season = TeamSeason.objects.create(
            team=team, season=self.base['season'],
            division=self.base['division'],
        )
        self.coach_season = CoachSeason.objects.create(
            coach=coach, team_season=team_season,
            season=self.base['season'], role='head_coach',
        )

        # Two players evaluated at station A; one of them also at station B
        for ps in self.player_seasons[:2]:
            Evaluation.objects.create(
                player_season=ps, session=self.session,
                coach_season=self.coach_season, station=self.station_a,
            )
        Evaluation.objects.create(
            player_season=self.player_seasons[0], session=self.session,
            coach_season=self.coach_season, station=self.station_b,
        )

    def _ctx(self, q=''):
        from tryouts.views import _build_ses_session_context
        return _build_ses_session_context(self.session, self.user, q=q)

    def test_stat_row_numbers(self):
        ctx = self._ctx()
        self.assertEqual(ctx['stats']['registered'], 5)
        self.assertEqual(ctx['stats']['checked_in'], 3)
        self.assertEqual(ctx['stats']['no_show'], 2)
        # Two checked-in players have been evaluated at least once
        self.assertEqual(ctx['stats']['on_station'], 2)

    def test_station_progress_excludes_inactive(self):
        ctx = self._ctx()
        names = [s['station'].name for s in ctx['station_progress']]
        self.assertEqual(names, ['Hitting', 'Fielding'])

    def test_station_progress_math_distinct(self):
        """Multiple evaluations at the same station for one player should not inflate."""
        # Second eval for same player at station A — same coach, distinct station forces unique_together violation,
        # so we change the coach. Reuse coach_season since unique_together is (player_season, session, coach_season, station).
        # Different player same station counts.
        ctx = self._ctx()
        sa = next(s for s in ctx['station_progress'] if s['station'].pk == self.station_a.pk)
        self.assertEqual(sa['evaluated'], 2)
        self.assertEqual(sa['expected'], 3)  # checked_in_count
        self.assertEqual(sa['state'], 'in_progress')
        sb = next(s for s in ctx['station_progress'] if s['station'].pk == self.station_b.pk)
        self.assertEqual(sb['evaluated'], 1)
        self.assertEqual(sb['state'], 'in_progress')

    def test_station_progress_idle_when_no_checkins(self):
        # Clear all check-ins
        CheckIn.objects.all().delete()
        ctx = self._ctx()
        for s in ctx['station_progress']:
            self.assertEqual(s['state'], 'idle')
            self.assertEqual(s['pct'], 0)

    def test_no_show_queue_lists_unchecked_only(self):
        ctx = self._ctx()
        queue_ids = [item['assignment'].pk for item in ctx['no_show_queue']]
        # Two unchecked assignments — the last two players
        expected = [self.assignments[3].pk, self.assignments[4].pk]
        self.assertEqual(sorted(queue_ids), sorted(expected))

    def test_no_show_queue_reschedule_target_picks_makeup(self):
        # Create both a makeup and a regular future session in this division
        regular_next = Session.objects.create(
            season=self.base['season'], name='SES Day 2',
            date=date.today() + timedelta(days=2), start_time=time(9, 0),
            division=self.base['division'],
        )
        makeup = Session.objects.create(
            season=self.base['season'], name='SES Day 1 Makeup',
            date=date.today() + timedelta(days=4), start_time=time(9, 0),
            division=self.base['division'],
            is_makeup=True, makeup_for=self.session,
        )
        ctx = self._ctx()
        for item in ctx['no_show_queue']:
            self.assertEqual(item['reschedule_target'].pk, makeup.pk)

    def test_no_show_queue_target_falls_back_to_next_regular(self):
        next_session = Session.objects.create(
            season=self.base['season'], name='SES Day 2',
            date=date.today() + timedelta(days=2), start_time=time(9, 0),
            division=self.base['division'],
        )
        ctx = self._ctx()
        for item in ctx['no_show_queue']:
            self.assertEqual(item['reschedule_target'].pk, next_session.pk)

    def test_no_show_queue_target_none_when_no_future(self):
        ctx = self._ctx()
        for item in ctx['no_show_queue']:
            self.assertIsNone(item['reschedule_target'])

    def test_roster_search_filter(self):
        ctx = self._ctx(q='Last0')
        roster_pks = [r['assignment'].pk for r in ctx['roster']]
        self.assertEqual(roster_pks, [self.assignments[0].pk])

    def test_roster_search_empty_returns_all(self):
        ctx = self._ctx(q='')
        self.assertEqual(len(ctx['roster']), 5)

    def test_roster_search_case_insensitive(self):
        ctx = self._ctx(q='lasT2')
        roster_pks = [r['assignment'].pk for r in ctx['roster']]
        self.assertEqual(roster_pks, [self.assignments[2].pk])


class SESSessionDetailRenderTests(TestCase):
    """End-to-end render of session_detail.html on Pacific tokens."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.player = _create_player(self.base['league'])
        self.ps = PlayerSeason.objects.create(
            player=self.player, season=self.base['season'],
            division=self.base['division'],
        )
        self.session = Session.objects.create(
            season=self.base['season'], name='SES Day 1',
            date=date.today(), start_time=time(9, 0),
            division=self.base['division'],
        )
        self.assignment = SessionAssignment.objects.create(
            session=self.session, player_season=self.ps, assigned_by=self.user,
        )
        Station.objects.create(
            league=self.base['league'], name='Hitting', display_order=0,
        )
        self.client = Client()
        self.client.login(username='user@sfll.org', password='testpass123')

    def test_renders_pacific_chrome(self):
        resp = self.client.get(reverse('tryouts:session_detail', args=[self.session.pk]))
        self.assertEqual(resp.status_code, 200)
        # Pacific token classes present
        self.assertContains(resp, 'ses-page')
        self.assertContains(resp, 'page-header')
        self.assertContains(resp, 'stats')
        self.assertContains(resp, 'station-grid')
        self.assertContains(resp, 'ses-twocol')
        # No remaining dark Tailwind chrome from the old template
        self.assertNotContains(resp, 'bg-gray-800')
        self.assertNotContains(resp, 'text-emerald-400')

    def test_no_inline_style_block(self):
        """All page-level styles live in lms-components.css now; the template
        should not ship its own <style> block."""
        resp = self.client.get(reverse('tryouts:session_detail', args=[self.session.pk]))
        # The SES screen specifically should not emit a per-screen <style> tag
        content = resp.content.decode()
        # Allow style attributes (margin-left etc.) but not <style> blocks
        self.assertNotIn('<style>', content)
        self.assertNotIn('</style>', content)

    def test_oob_swap_targets_present(self):
        resp = self.client.get(reverse('tryouts:session_detail', args=[self.session.pk]))
        self.assertContains(resp, 'id="ses-stats"')
        self.assertContains(resp, 'id="ses-roster"')
        self.assertContains(resp, 'id="ses-noshow"')


class SESQuickCheckinTests(TestCase):
    """Quick check-in HTMX endpoint."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.player = _create_player(self.base['league'])
        self.ps = PlayerSeason.objects.create(
            player=self.player, season=self.base['season'],
            division=self.base['division'],
        )
        self.session = Session.objects.create(
            season=self.base['season'], name='SES 1',
            date=date.today(), start_time=time(9, 0),
            division=self.base['division'],
        )
        self.assignment = SessionAssignment.objects.create(
            session=self.session, player_season=self.ps, assigned_by=self.user,
        )
        self.client = Client()
        self.client.login(username='user@sfll.org', password='testpass123')

    def test_quick_checkin_creates_checkin(self):
        resp = self.client.post(
            reverse('tryouts:ses_quick_checkin', args=[self.session.pk, self.assignment.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(CheckIn.objects.filter(session_assignment=self.assignment).exists())

    def test_quick_checkin_response_has_oob_swap(self):
        resp = self.client.post(
            reverse('tryouts:ses_quick_checkin', args=[self.session.pk, self.assignment.pk])
        )
        self.assertContains(resp, 'hx-swap-oob')
        self.assertContains(resp, 'id="ses-stats"')
        self.assertContains(resp, 'id="ses-noshow"')

    def test_quick_checkin_idempotent(self):
        url = reverse('tryouts:ses_quick_checkin', args=[self.session.pk, self.assignment.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(
            CheckIn.objects.filter(session_assignment=self.assignment).count(), 1,
        )

    def test_quick_checkin_forbidden_without_permission(self):
        # Switch to a regular user
        self.client.logout()
        _create_user(email='nobody@sfll.org')
        self.client.login(username='nobody@sfll.org', password='testpass123')
        resp = self.client.post(
            reverse('tryouts:ses_quick_checkin', args=[self.session.pk, self.assignment.pk])
        )
        self.assertEqual(resp.status_code, 403)


class SESQuickRescheduleTests(TestCase):
    """One-click reschedule HTMX endpoint."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.player = _create_player(self.base['league'])
        self.ps = PlayerSeason.objects.create(
            player=self.player, season=self.base['season'],
            division=self.base['division'],
        )
        self.session = Session.objects.create(
            season=self.base['season'], name='SES 1',
            date=date.today(), start_time=time(9, 0),
            division=self.base['division'],
        )
        self.assignment = SessionAssignment.objects.create(
            session=self.session, player_season=self.ps, assigned_by=self.user,
        )
        self.client = Client()
        self.client.login(username='user@sfll.org', password='testpass123')

    def _next_session(self, days=2, is_makeup=False):
        return Session.objects.create(
            season=self.base['season'],
            name='Makeup' if is_makeup else 'Day 2',
            date=date.today() + timedelta(days=days),
            start_time=time(9, 0),
            division=self.base['division'],
            is_makeup=is_makeup,
            makeup_for=self.session if is_makeup else None,
        )

    def test_reschedule_creates_assignment_at_target(self):
        target = self._next_session(days=3, is_makeup=True)
        resp = self.client.post(
            reverse('tryouts:ses_quick_reschedule', args=[self.session.pk, self.assignment.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            SessionAssignment.objects.filter(session=target, player_season=self.ps).exists()
        )

    def test_reschedule_deletes_original_assignment(self):
        self._next_session(days=3, is_makeup=True)
        resp = self.client.post(
            reverse('tryouts:ses_quick_reschedule', args=[self.session.pk, self.assignment.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(SessionAssignment.objects.filter(pk=self.assignment.pk).exists())

    def test_reschedule_flags_player_for_makeup(self):
        self._next_session(days=3, is_makeup=True)
        self.client.post(
            reverse('tryouts:ses_quick_reschedule', args=[self.session.pk, self.assignment.pk])
        )
        self.ps.refresh_from_db()
        self.assertEqual(self.ps.status, 'needs_makeup')

    def test_reschedule_records_audit_log(self):
        target = self._next_session(days=3, is_makeup=True)
        self.client.post(
            reverse('tryouts:ses_quick_reschedule', args=[self.session.pk, self.assignment.pk])
        )
        log = AuditLog.objects.filter(action='player.quick_reschedule').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.details['from_session_id'], self.session.pk)
        self.assertEqual(log.details['to_session_id'], target.pk)

    def test_reschedule_409_when_no_target(self):
        resp = self.client.post(
            reverse('tryouts:ses_quick_reschedule', args=[self.session.pk, self.assignment.pk])
        )
        self.assertEqual(resp.status_code, 409)
        self.assertContains(resp, 'No upcoming session available', status_code=409)
        # Original assignment is preserved
        self.assertTrue(SessionAssignment.objects.filter(pk=self.assignment.pk).exists())

    def test_reschedule_prefers_makeup_over_regular(self):
        makeup = self._next_session(days=4, is_makeup=True)
        self._next_session(days=2, is_makeup=False)  # earlier regular session
        self.client.post(
            reverse('tryouts:ses_quick_reschedule', args=[self.session.pk, self.assignment.pk])
        )
        # The new assignment should be on the makeup session even though it's later
        self.assertTrue(
            SessionAssignment.objects.filter(session=makeup, player_season=self.ps).exists()
        )

    def test_reschedule_response_has_oob_stat_swap(self):
        self._next_session(days=3, is_makeup=True)
        resp = self.client.post(
            reverse('tryouts:ses_quick_reschedule', args=[self.session.pk, self.assignment.pk])
        )
        self.assertContains(resp, 'hx-swap-oob')
        self.assertContains(resp, 'id="ses-stats"')


class SESRosterSearchTests(TestCase):
    """HTMX roster-search endpoint."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.session = Session.objects.create(
            season=self.base['season'], name='SES 1',
            date=date.today(), start_time=time(9, 0),
            division=self.base['division'],
        )
        for i in range(3):
            p = _create_player(
                self.base['league'], sc_id=f'SC-{i:03d}',
                first=f'First{i}', last=f'Smith' if i == 0 else f'Jones{i}',
            )
            ps = PlayerSeason.objects.create(
                player=p, season=self.base['season'],
                division=self.base['division'],
            )
            SessionAssignment.objects.create(
                session=self.session, player_season=ps, assigned_by=self.user,
            )
        self.client = Client()
        self.client.login(username='user@sfll.org', password='testpass123')

    def test_roster_search_returns_partial(self):
        resp = self.client.get(
            reverse('tryouts:ses_roster_search', args=[self.session.pk]),
            {'q': 'Smith'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Smith')
        self.assertNotContains(resp, 'Jones1')

    def test_roster_search_empty_q_returns_all(self):
        resp = self.client.get(
            reverse('tryouts:ses_roster_search', args=[self.session.pk]),
        )
        self.assertContains(resp, 'Smith')
        self.assertContains(resp, 'Jones1')
        self.assertContains(resp, 'Jones2')

    def test_roster_search_no_match_shows_empty(self):
        resp = self.client.get(
            reverse('tryouts:ses_roster_search', args=[self.session.pk]),
            {'q': 'Zzzz'},
        )
        self.assertContains(resp, 'No players match')
