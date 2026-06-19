"""Tests for the tryouts app — Session, SessionAssignment, CheckIn models and views."""

from datetime import date, time, timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from players.models import Division, League, Player, PlayerSeason, Season, Station
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


class SessionDetailContextTests(TestCase):
    """Regression tests for session_detail context correctness (SFLL-111 Codex findings)."""

    def setUp(self):
        from accounts.models import Coach, CoachSeason
        from players.models import Station, Team, TeamSeason

        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.client = Client()
        self.client.login(username='user@sfll.org', password='testpass123')

        league = self.base['league']
        season = self.base['season']
        division = self.base['division']

        self.station_a = Station.objects.create(
            league=league, name='Hitting', display_order=0, eval_fields=[]
        )
        self.station_b = Station.objects.create(
            league=league, name='Fielding', display_order=1, eval_fields=[]
        )

        # Two players
        p1 = _create_player(league, sc_id='SC-001', first='Alice', last='A')
        p2 = _create_player(league, sc_id='SC-002', first='Bob', last='B')
        self.ps1 = PlayerSeason.objects.create(player=p1, season=season, division=division)
        self.ps2 = PlayerSeason.objects.create(player=p2, season=season, division=division)

        # Coach setup for Evaluation objects
        team = Team.objects.create(league=league, name='Marlins')
        team_season = TeamSeason.objects.create(team=team, season=season, division=division)
        coach_user = _create_user(email='coach@sfll.org')
        coach = Coach.objects.create(user=coach_user, league=league)
        self.coach_season = CoachSeason.objects.create(
            coach=coach, team_season=team_season, season=season, role='head_coach'
        )

    def _make_session(self, delta_days):
        """Return a session delta_days from today (negative = past, positive = future)."""
        return Session.objects.create(
            season=self.base['season'], name='SES Test',
            date=date.today() + timedelta(days=delta_days),
            start_time=time(9, 0), division=self.base['division'],
        )

    def _assign_and_checkin(self, session, player_season, checkin=True):
        a = SessionAssignment.objects.create(
            session=session, player_season=player_season, assigned_by=self.user
        )
        if checkin:
            CheckIn.objects.create(session_assignment=a, checked_in_by=self.user)
        return a

    def test_past_session_shows_noshow_count(self):
        """session_is_past=True: unchecked players become no-shows."""
        session = self._make_session(-1)  # yesterday
        self._assign_and_checkin(session, self.ps1, checkin=True)
        self._assign_and_checkin(session, self.ps2, checkin=False)

        resp = self.client.get(reverse('tryouts:session_detail', args=[session.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['session_is_past'])
        self.assertEqual(resp.context['noshow_count'], 1)
        self.assertEqual(resp.context['pending_count'], 0)

    def test_future_session_noshow_count_is_zero(self):
        """session_is_past=False: unchecked players are pending arrivals, not no-shows."""
        session = self._make_session(1)  # tomorrow
        self._assign_and_checkin(session, self.ps1, checkin=True)
        self._assign_and_checkin(session, self.ps2, checkin=False)

        resp = self.client.get(reverse('tryouts:session_detail', args=[session.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['session_is_past'])
        self.assertEqual(resp.context['noshow_count'], 0)
        self.assertEqual(resp.context['pending_count'], 1)

    def test_eval_count_uses_player_station_pairs(self):
        """eval_count must count distinct (player_season, station) completions.

        With 2 players and 2 stations, if both players are evaluated at both
        stations, eval_count should be 4 (matching evals_expected = 2 * 2).
        A second coach evaluating the same player at the same station must not
        inflate the count beyond 1 for that pair.
        """
        from evaluations.models import Evaluation

        session = self._make_session(-1)
        self._assign_and_checkin(session, self.ps1)
        self._assign_and_checkin(session, self.ps2)

        # ps1 at station_a, ps2 at station_a — 2 distinct pairs
        Evaluation.objects.create(
            player_season=self.ps1, session=session,
            coach_season=self.coach_season, station=self.station_a, scores={}
        )
        Evaluation.objects.create(
            player_season=self.ps2, session=session,
            coach_season=self.coach_season, station=self.station_a, scores={}
        )

        resp = self.client.get(reverse('tryouts:session_detail', args=[session.pk]))
        ctx = resp.context
        # 2 players, 2 stations → expected = 4; only 2 evals done
        self.assertEqual(ctx['evals_expected'], 4)
        self.assertEqual(ctx['eval_count'], 2)
        self.assertEqual(ctx['evals_pending'], 2)

    def test_eval_count_distinct_pairs_not_raw_rows(self):
        """Two evaluations for the same player×station (different coaches) count as 1."""
        from accounts.models import Coach, CoachSeason
        from players.models import Team, TeamSeason
        from evaluations.models import Evaluation

        season = self.base['season']
        league = self.base['league']
        session = self._make_session(-1)
        self._assign_and_checkin(session, self.ps1)

        # Second coach for the same session
        team2 = Team.objects.create(league=league, name='Cubs')
        team_season2 = TeamSeason.objects.create(
            team=team2, season=season, division=self.base['division']
        )
        coach_user2 = _create_user(email='coach2@sfll.org')
        coach2 = Coach.objects.create(user=coach_user2, league=league)
        coach_season2 = CoachSeason.objects.create(
            coach=coach2, team_season=team_season2, season=season, role='assistant_coach'
        )

        # Same (player_season, station) from two different coaches → 2 rows, 1 distinct pair
        Evaluation.objects.create(
            player_season=self.ps1, session=session,
            coach_season=self.coach_season, station=self.station_a, scores={}
        )
        Evaluation.objects.create(
            player_season=self.ps1, session=session,
            coach_season=coach_season2, station=self.station_a, scores={}
        )

        resp = self.client.get(reverse('tryouts:session_detail', args=[session.pk]))
        ctx = resp.context
        # 1 player, 2 stations → expected = 2; only 1 distinct pair evaluated
        self.assertEqual(ctx['evals_expected'], 2)
        self.assertEqual(ctx['eval_count'], 1)


class ReassignPlayerViewTests(TestCase):
    """Verify reassign_player POST is scoped to same season/division."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.client = Client()
        self.client.login(username='user@sfll.org', password='testpass123')

        self.player = _create_player(self.base['league'])
        self.ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.base['season'],
            division=self.base['division'],
        )
        self.source_session = Session.objects.create(
            season=self.base['season'],
            name='SES Day 1',
            date=date(2026, 3, 28),
            start_time=time(9, 0),
            division=self.base['division'],
        )
        self.assignment = SessionAssignment.objects.create(
            session=self.source_session,
            player_season=self.ps,
        )
        # Valid target: same season/division
        self.valid_target = Session.objects.create(
            season=self.base['season'],
            name='SES Day 2',
            date=date(2026, 4, 5),
            start_time=time(9, 0),
            division=self.base['division'],
        )
        # Out-of-scope target: different division
        other_division = Division.objects.create(
            league=self.base['league'], name='Minors', display_order=1,
        )
        self.rogue_target = Session.objects.create(
            season=self.base['season'],
            name='Minors SES 1',
            date=date(2026, 4, 5),
            start_time=time(9, 0),
            division=other_division,
        )

    def _url(self):
        return reverse(
            'tryouts:reassign_player',
            kwargs={'pk': self.source_session.pk, 'assignment_id': self.assignment.pk},
        )

    def test_valid_reassignment_succeeds(self):
        resp = self.client.post(self._url(), {'target_session': self.valid_target.pk})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            SessionAssignment.objects.filter(
                session=self.valid_target, player_season=self.ps
            ).exists()
        )

    def test_out_of_scope_session_rejected(self):
        # Crafted POST with a session from a different division — must return 404
        resp = self.client.post(self._url(), {'target_session': self.rogue_target.pk})
        self.assertEqual(resp.status_code, 404)
        # Player must remain in the original session
        self.assertTrue(
            SessionAssignment.objects.filter(
                session=self.source_session, player_season=self.ps
            ).exists()
        )
