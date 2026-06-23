"""Tests for SFLL-117 — Tweaks panel + ⌘K command palette.

Covers:
  • The new User.power_user_mode flag default + admin gating
  • The /api/cmdk-search/ endpoint: auth required, flag-gated, role-filtered
    pages, player and family results
  • base.html feature-flag rendering: partials only appear when flag is on
"""

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User, UserRole
from players.models import Division, League, Player, PlayerSeason, Season


def _league():
    return League.objects.create(name='San Francisco Little League', short_name='SFLL')


def _season(league, is_active=True):
    return Season.objects.create(
        league=league, name='Spring 2026', year=2026,
        season_type='spring', is_active=is_active,
    )


def _user(email='power@sfll.org', power=False, **kwargs):
    return User.objects.create_user(
        username=email, email=email,
        first_name=kwargs.get('first_name', 'Pat'),
        last_name=kwargs.get('last_name', 'User'),
        password='testpass123',
        power_user_mode=power,
    )


def _player(league, first, last, sportsconnect_id):
    return Player.objects.create(
        league=league, sportsconnect_player_id=sportsconnect_id,
        first_name=first, last_name=last,
    )


class PowerUserModeFieldTests(TestCase):
    def test_default_is_false(self):
        user = _user()
        self.assertFalse(user.power_user_mode)

    def test_can_set_true(self):
        user = _user(power=True)
        user.refresh_from_db()
        self.assertTrue(user.power_user_mode)

    def test_field_persists_independently_of_admin(self):
        """Power-user mode is a UX flag, not a permission. Toggling it
        must NOT touch is_staff or is_superuser."""
        user = _user(power=True)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)


class CmdkSearchEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.league = _league()
        self.season = _season(self.league)
        self.div = Division.objects.create(
            league=self.league, name='Majors', display_order=0,
        )
        self.player = _player(self.league, 'Sammy', 'Sosa', 'SC-1')
        PlayerSeason.objects.create(
            player=self.player, season=self.season, division=self.div,
            account_name='Sosa Household', account_email='sosa@example.com',
        )
        self.other = _player(self.league, 'Maria', 'Lopez', 'SC-2')
        PlayerSeason.objects.create(
            player=self.other, season=self.season, division=self.div,
            account_name='Lopez Family', account_email='lopez@example.com',
        )

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse('cmdk_search'))
        # login_required redirects to LOGIN_URL
        self.assertEqual(resp.status_code, 302)

    def test_non_power_user_forbidden(self):
        user = _user(email='plain@sfll.org', power=False)
        self.client.force_login(user)
        resp = self.client.get(reverse('cmdk_search'))
        self.assertEqual(resp.status_code, 403)

    def test_power_user_gets_payload(self):
        user = _user(email='power@sfll.org', power=True)
        self.client.force_login(user)
        resp = self.client.get(reverse('cmdk_search'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('pages', data)
        self.assertIn('players', data)
        self.assertIn('families', data)
        # Empty query returns all pages the user can reach.
        page_titles = {p['title'] for p in data['pages']}
        self.assertIn('Dashboard', page_titles)
        self.assertIn('Roster', page_titles)

    def test_non_admin_excluded_from_admin_pages(self):
        user = _user(email='nonadmin@sfll.org', power=True)
        self.client.force_login(user)
        resp = self.client.get(reverse('cmdk_search'))
        page_titles = {p['title'] for p in resp.json()['pages']}
        self.assertNotIn('Audit log', page_titles)
        self.assertNotIn('Configuration', page_titles)

    def test_admin_sees_admin_pages(self):
        user = _user(email='admin@sfll.org', power=True)
        UserRole.objects.create(user=user, league=self.league, role='cto')
        self.client.force_login(user)
        resp = self.client.get(reverse('cmdk_search'))
        page_titles = {p['title'] for p in resp.json()['pages']}
        self.assertIn('Audit log', page_titles)
        self.assertIn('Configuration', page_titles)

    def test_player_query_filters_results(self):
        user = _user(email='power@sfll.org', power=True)
        self.client.force_login(user)
        resp = self.client.get(reverse('cmdk_search'), {'q': 'sosa'})
        players = resp.json()['players']
        names = [p['title'] for p in players]
        self.assertTrue(any('Sosa' in n for n in names))
        self.assertFalse(any('Lopez' in n for n in names))

    def test_player_full_name_first_last(self):
        """'Sammy Sosa' (space-separated) returns the correct player."""
        user = _user(email='power2@sfll.org', power=True)
        self.client.force_login(user)
        resp = self.client.get(reverse('cmdk_search'), {'q': 'Sammy Sosa'})
        players = resp.json()['players']
        self.assertEqual(len(players), 1)
        self.assertIn('Sosa', players[0]['title'])

    def test_player_full_name_last_comma_first(self):
        """'Sosa, Sammy' (Last, First) returns the correct player."""
        user = _user(email='power3@sfll.org', power=True)
        self.client.force_login(user)
        resp = self.client.get(reverse('cmdk_search'), {'q': 'Sosa, Sammy'})
        players = resp.json()['players']
        self.assertEqual(len(players), 1)
        self.assertIn('Sosa', players[0]['title'])

    def test_player_full_name_no_false_positive(self):
        """'Sammy Lopez' matches neither player — both tokens must align."""
        user = _user(email='power4@sfll.org', power=True)
        self.client.force_login(user)
        resp = self.client.get(reverse('cmdk_search'), {'q': 'Sammy Lopez'})
        self.assertEqual(resp.json()['players'], [])

    def test_family_results_use_account_name(self):
        user = _user(email='power@sfll.org', power=True)
        self.client.force_login(user)
        resp = self.client.get(reverse('cmdk_search'), {'q': 'household'})
        families = resp.json()['families']
        self.assertTrue(any(f['title'] == 'Sosa Household' for f in families))
        # Subtitle includes the player count.
        sosa = next(f for f in families if f['title'] == 'Sosa Household')
        self.assertIn('1 player', sosa['subtitle'])
        # Deep-link uses quote_via=quote so spaces are encoded as %20, not +.
        self.assertIn('account=Sosa%20Household', sosa['url'])

    def test_superuser_treated_as_admin(self):
        user = _user(email='su@sfll.org', power=True)
        user.is_superuser = True
        user.save()
        self.client.force_login(user)
        resp = self.client.get(reverse('cmdk_search'))
        page_titles = {p['title'] for p in resp.json()['pages']}
        self.assertIn('Audit log', page_titles)


class BaseTemplateFeatureFlagTests(TestCase):
    def setUp(self):
        self.client = Client()
        _league()
        # An active season is enough to render the dashboard without errors.
        Season.objects.create(
            league=League.objects.first(), name='Spring 2026', year=2026,
            season_type='spring', is_active=True,
        )

    def test_partials_hidden_for_plain_user(self):
        user = _user(email='plain@sfll.org', power=False)
        self.client.force_login(user)
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertNotIn('id="lms-tweaks"', body)
        self.assertNotIn('id="lms-cmdk"', body)
        self.assertNotIn('lms-tweaks-cmdk.css', body)

    def test_partials_visible_for_power_user(self):
        user = _user(email='power@sfll.org', power=True)
        self.client.force_login(user)
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('id="lms-tweaks"', body)
        self.assertIn('id="lms-cmdk"', body)
        self.assertIn('lms-tweaks-cmdk.css', body)
        self.assertIn('lms-tweaks-panel.js', body)
        self.assertIn('lms-cmdk.js', body)
        # Topbar exposes the real trigger buttons, not the placeholder kbd.
        self.assertIn('id="lms-cmdk-trigger"', body)
        self.assertIn('id="lms-tweaks-trigger"', body)

    def test_topbar_shows_placeholder_for_plain_user(self):
        user = _user(email='plain@sfll.org', power=False)
        self.client.force_login(user)
        resp = self.client.get(reverse('dashboard'))
        body = resp.content.decode()
        self.assertIn('lms-topbar__cmdk', body)
        self.assertNotIn('id="lms-cmdk-trigger"', body)


class RosterFilterTests(TestCase):
    """SFLL-117 added ?q= and ?account= filters to players:index so the
    palette can deep-link into the roster. Verify they actually filter."""

    def setUp(self):
        self.client = Client()
        self.league = _league()
        self.season = _season(self.league)
        self.div = Division.objects.create(
            league=self.league, name='Majors', display_order=0,
        )
        self.p1 = _player(self.league, 'Sammy', 'Sosa', 'SC-1')
        self.ps1 = PlayerSeason.objects.create(
            player=self.p1, season=self.season, division=self.div,
            account_name='Sosa Household',
        )
        self.p2 = _player(self.league, 'Maria', 'Lopez', 'SC-2')
        self.ps2 = PlayerSeason.objects.create(
            player=self.p2, season=self.season, division=self.div,
            account_name='Lopez Family',
        )
        self.user = _user(email='roster@sfll.org')
        self.client.force_login(self.user)

    def test_q_filter_matches_last_name(self):
        resp = self.client.get(reverse('players:index'), {'q': 'sosa'})
        self.assertEqual(resp.status_code, 200)
        ids = {ps.id for ps in resp.context['player_seasons']}
        self.assertEqual(ids, {self.ps1.id})

    def test_account_filter_exact(self):
        resp = self.client.get(reverse('players:index'), {'account': 'Lopez Family'})
        self.assertEqual(resp.status_code, 200)
        ids = {ps.id for ps in resp.context['player_seasons']}
        self.assertEqual(ids, {self.ps2.id})

    def test_no_filter_returns_all(self):
        resp = self.client.get(reverse('players:index'))
        self.assertEqual(resp.status_code, 200)
        ids = {ps.id for ps in resp.context['player_seasons']}
        self.assertEqual(ids, {self.ps1.id, self.ps2.id})

    def test_q_filter_last_comma_first_matches_one(self):
        """Palette deep-links use 'Last, First' format; roster must match it."""
        resp = self.client.get(reverse('players:index'), {'q': 'Sosa, Sammy'})
        self.assertEqual(resp.status_code, 200)
        ids = {ps.id for ps in resp.context['player_seasons']}
        self.assertEqual(ids, {self.ps1.id})

    def test_q_filter_last_comma_first_no_false_positive(self):
        """'Lopez, Sammy' matches neither player — last AND first must both align."""
        resp = self.client.get(reverse('players:index'), {'q': 'Lopez, Sammy'})
        self.assertEqual(resp.status_code, 200)
        ids = {ps.id for ps in resp.context['player_seasons']}
        self.assertEqual(ids, set())

    def test_cmdk_player_url_round_trips_via_roster(self):
        """The URL the palette emits for a player must return exactly that player."""
        power_user = _user(email='pu@sfll.org', power=True)
        self.client.force_login(power_user)
        resp = self.client.get(reverse('cmdk_search'), {'q': 'sosa'})
        players = resp.json()['players']
        sosa = next(p for p in players if 'Sosa' in p['title'])
        # Crack the URL the palette would navigate to.
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(sosa['url'])
        q_param = parse_qs(parsed.query).get('q', [None])[0]
        self.assertIsNotNone(q_param)
        # Navigate to that URL as a regular logged-in user.
        self.client.force_login(self.user)
        roster_resp = self.client.get(reverse('players:index'), {'q': q_param})
        self.assertEqual(roster_resp.status_code, 200)
        ids = {ps.id for ps in roster_resp.context['player_seasons']}
        self.assertEqual(ids, {self.ps1.id})
