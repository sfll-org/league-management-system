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
