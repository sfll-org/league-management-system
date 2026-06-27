"""Tests for the accounts app — User, UserRole, Coach, CoachSeason models and auth views."""

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import Coach, CoachSeason, User, UserRole
from players.models import Division, League, Season, Team, TeamSeason


class UserModelFactory:
    """Shared helper methods for creating test data."""

    @staticmethod
    def create_league():
        return League.objects.create(
            name='San Francisco Little League',
            short_name='SFLL',
        )

    @staticmethod
    def create_season(league, is_active=True):
        return Season.objects.create(
            league=league,
            name='Spring 2026',
            year=2026,
            season_type='spring',
            is_active=is_active,
        )

    @staticmethod
    def create_division(league, name='Majors', display_order=0):
        return Division.objects.create(
            league=league,
            name=name,
            display_order=display_order,
        )

    @staticmethod
    def create_user(email='coach@sfll.org', first_name='Test', last_name='User', password='testpass123'):
        return User.objects.create_user(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
        )


class UserModelTests(TestCase):
    """Tests for the custom User model."""

    def test_create_user_email_based(self):
        user = User.objects.create_user(
            username='user@test.com',
            email='user@test.com',
            first_name='Jane',
            last_name='Doe',
            password='testpass123',
        )
        self.assertEqual(user.email, 'user@test.com')
        self.assertTrue(user.check_password('testpass123'))

    def test_str_returns_email(self):
        user = UserModelFactory.create_user()
        self.assertEqual(str(user), 'coach@sfll.org')

    def test_email_unique(self):
        UserModelFactory.create_user(email='dupe@sfll.org')
        with self.assertRaises(Exception):
            UserModelFactory.create_user(email='dupe@sfll.org')

    def test_username_field_is_email(self):
        self.assertEqual(User.USERNAME_FIELD, 'email')

    def test_required_fields(self):
        self.assertIn('first_name', User.REQUIRED_FIELDS)
        self.assertIn('last_name', User.REQUIRED_FIELDS)


class UserRoleModelTests(TestCase):
    """Tests for the UserRole model."""

    def setUp(self):
        self.league = UserModelFactory.create_league()
        self.division = UserModelFactory.create_division(self.league)
        self.user = UserModelFactory.create_user()

    def test_create_role(self):
        role = UserRole.objects.create(
            user=self.user,
            league=self.league,
            role='head_coach',
            division=self.division,
        )
        self.assertEqual(role.role, 'head_coach')
        self.assertTrue(role.is_active)

    def test_unique_together_user_role_division(self):
        UserRole.objects.create(
            user=self.user,
            league=self.league,
            role='head_coach',
            division=self.division,
        )
        with self.assertRaises(Exception):
            UserRole.objects.create(
                user=self.user,
                league=self.league,
                role='head_coach',
                division=self.division,
            )

    def test_global_role_no_division(self):
        role = UserRole.objects.create(
            user=self.user,
            league=self.league,
            role='cto',
            division=None,
        )
        self.assertIsNone(role.division)

    def test_str_with_division(self):
        role = UserRole.objects.create(
            user=self.user,
            league=self.league,
            role='head_coach',
            division=self.division,
        )
        self.assertIn('Majors', str(role))
        self.assertIn('coach@sfll.org', str(role))

    def test_str_global(self):
        role = UserRole.objects.create(
            user=self.user,
            league=self.league,
            role='cto',
            division=None,
        )
        self.assertIn('Global', str(role))

    def test_role_choices_count(self):
        self.assertEqual(len(UserRole.ROLE_CHOICES), 10)

    def test_global_roles_list(self):
        expected = [
            'cto', 'ses_manager', 'vp_player_agents', 'president', 'treasurer',
        ]
        self.assertEqual(UserRole.GLOBAL_ROLES, expected)

    def test_treasurer_role_choice_present(self):
        # SFLL-95 — treasurer is the role that gates the read-only balance
        # view on the family detail page.
        codes = [code for code, _ in UserRole.ROLE_CHOICES]
        self.assertIn('treasurer', codes)


class CoachModelTests(TestCase):
    """Tests for Coach and CoachSeason models."""

    def setUp(self):
        self.league = UserModelFactory.create_league()
        self.season = UserModelFactory.create_season(self.league)
        self.division = UserModelFactory.create_division(self.league)
        self.user = UserModelFactory.create_user()
        self.coach = Coach.objects.create(
            user=self.user,
            league=self.league,
        )
        self.team = Team.objects.create(league=self.league, name='Marlins')
        self.team_season = TeamSeason.objects.create(
            team=self.team,
            season=self.season,
            division=self.division,
        )

    def test_coach_str_full_name(self):
        self.assertIn('Test User', str(self.coach))

    def test_coach_str_email_fallback(self):
        user2 = UserModelFactory.create_user(
            email='noname@sfll.org', first_name='', last_name=''
        )
        coach2 = Coach.objects.create(user=user2, league=self.league)
        self.assertIn('noname@sfll.org', str(coach2))

    def test_coach_one_to_one(self):
        self.assertEqual(self.user.coach_profile, self.coach)

    def test_coach_season_create(self):
        cs = CoachSeason.objects.create(
            coach=self.coach,
            team_season=self.team_season,
            season=self.season,
            role='head_coach',
        )
        self.assertEqual(cs.role, 'head_coach')
        self.assertFalse(cs.is_drafter)

    def test_coach_season_unique_together(self):
        CoachSeason.objects.create(
            coach=self.coach,
            team_season=self.team_season,
            season=self.season,
            role='head_coach',
        )
        with self.assertRaises(Exception):
            CoachSeason.objects.create(
                coach=self.coach,
                team_season=self.team_season,
                season=self.season,
                role='assistant_coach',
            )

    def test_coach_season_str(self):
        cs = CoachSeason.objects.create(
            coach=self.coach,
            team_season=self.team_season,
            season=self.season,
            role='head_coach',
        )
        result = str(cs)
        self.assertIn('Head Coach', result)


class LoginViewTests(TestCase):
    """Tests for the login and logout views."""

    def setUp(self):
        self.client = Client()
        self.user = UserModelFactory.create_user(
            email='login@sfll.org', password='testpass123'
        )

    def test_login_page_renders(self):
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 200)

    def test_login_page_uses_standalone_chrome(self):
        resp = self.client.get(reverse('accounts:login'))
        self.assertNotContains(resp, 'lms-sidebar')
        self.assertNotContains(resp, 'lms-topbar')
        self.assertNotContains(resp, 'lms-main')

    def test_login_page_does_not_leak_template_comments(self):
        resp = self.client.get(reverse('accounts:login'))
        self.assertNotContains(resp, '{#')
        self.assertNotContains(resp, '#}')
        self.assertNotContains(resp, 'SFLL-92')

    def test_login_success_redirects(self):
        resp = self.client.post(reverse('accounts:login'), {
            'email': 'login@sfll.org',
            'password': 'testpass123',
        })
        self.assertEqual(resp.status_code, 302)

    def test_login_bad_password(self):
        resp = self.client.post(reverse('accounts:login'), {
            'email': 'login@sfll.org',
            'password': 'wrongpassword',
        })
        self.assertEqual(resp.status_code, 200)  # re-renders form

    def test_authenticated_user_redirected_from_login(self):
        self.client.login(username='login@sfll.org', password='testpass123')
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 302)

    def test_login_page_has_no_register_link(self):
        # SFLL-143: public registration removed; login page must not link to /accounts/register/
        resp = self.client.get(reverse('accounts:login'))
        self.assertNotContains(resp, 'accounts:register')
        self.assertNotContains(resp, '/accounts/register/')

    def test_register_route_does_not_exist(self):
        # SFLL-143: /accounts/register/ must return 404
        resp = self.client.get('/accounts/register/')
        self.assertEqual(resp.status_code, 404)

    def test_logout_redirects(self):
        self.client.login(username='login@sfll.org', password='testpass123')
        resp = self.client.get(reverse('accounts:logout'))
        self.assertEqual(resp.status_code, 302)
