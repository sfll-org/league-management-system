"""Tests for the players app — League, Season, Division, Station, Player, PlayerSeason, Team, TeamSeason, plus Family Detail (SFLL-95) and Print surfaces (SFLL-114/SFLL-129)."""

import os
from datetime import date, timedelta

from django.test import TestCase, SimpleTestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Coach, CoachSeason, User, UserRole
from communications.models import EmailLog
from players.models import (
    Division,
    League,
    Player,
    PlayerSeason,
    Season,
    Station,
    Team,
    TeamSeason,
)
from players.views import encode_family_key
from tryouts.models import Session


def _create_league():
    return League.objects.create(
        name="San Francisco Little League",
        short_name="SFLL",
    )


def _create_user(email="test@sfll.org", password="testpass123"):
    return User.objects.create_user(
        username=email,
        email=email,
        first_name="Test",
        last_name="User",
        password=password,
    )


class LeagueModelTests(TestCase):
    def test_str_returns_short_name(self):
        league = _create_league()
        self.assertEqual(str(league), "SFLL")

    def test_defaults(self):
        league = _create_league()
        self.assertEqual(league.timezone, "America/New_York")
        self.assertEqual(league.sportsconnect_sync_interval_minutes, 60)


class SeasonModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()

    def test_str_format(self):
        season = Season.objects.create(
            league=self.league,
            name="Spring 2026",
            year=2026,
            season_type="spring",
        )
        self.assertEqual(str(season), "Spring 2026 (2026)")

    def test_default_flags(self):
        season = Season.objects.create(
            league=self.league,
            name="Fall 2025",
            year=2025,
            season_type="fall",
        )
        self.assertFalse(season.is_active)
        self.assertFalse(season.registration_open)
        self.assertFalse(season.draft_complete)

    def test_ordering(self):
        Season.objects.create(
            league=self.league, name="S1", year=2025, season_type="spring"
        )
        Season.objects.create(
            league=self.league, name="S2", year=2026, season_type="spring"
        )
        seasons = list(Season.objects.all())
        self.assertEqual(seasons[0].year, 2026)


class DivisionModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()

    def test_str(self):
        div = Division.objects.create(league=self.league, name="Majors")
        self.assertEqual(str(div), "Majors")

    def test_ordering_by_display_order(self):
        Division.objects.create(league=self.league, name="AA", display_order=2)
        Division.objects.create(league=self.league, name="Majors", display_order=0)
        Division.objects.create(league=self.league, name="AAA", display_order=1)
        divs = list(Division.objects.all())
        self.assertEqual([d.name for d in divs], ["Majors", "AAA", "AA"])

    def test_has_leagues_default(self):
        div = Division.objects.create(league=self.league, name="AA")
        self.assertFalse(div.has_leagues)
        self.assertEqual(div.league_names, [])


class StationModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()

    def test_str(self):
        station = Station.objects.create(
            league=self.league,
            name="Hitting",
            display_order=0,
        )
        self.assertEqual(str(station), "Hitting (SFLL)")

    def test_eval_fields_default(self):
        station = Station.objects.create(
            league=self.league,
            name="Fielding",
        )
        self.assertEqual(station.eval_fields, [])

    def test_eval_fields_json(self):
        fields = [
            {"key": "power", "label": "Power", "type": "int", "min": 1, "max": 10}
        ]
        station = Station.objects.create(
            league=self.league,
            name="Hitting",
            eval_fields=fields,
        )
        self.assertEqual(station.eval_fields[0]["key"], "power")


class PlayerModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()

    def test_str(self):
        p = Player.objects.create(
            league=self.league,
            sportsconnect_player_id="SC-001",
            first_name="Jayden",
            last_name="Rodriguez",
        )
        self.assertEqual(str(p), "Jayden Rodriguez")

    def test_full_name_property(self):
        p = Player.objects.create(
            league=self.league,
            sportsconnect_player_id="SC-002",
            first_name="Aiden",
            last_name="Martinez",
        )
        self.assertEqual(p.full_name, "Aiden Martinez")

    def test_sportsconnect_player_id_unique(self):
        Player.objects.create(
            league=self.league,
            sportsconnect_player_id="SC-DUP",
            first_name="A",
            last_name="B",
        )
        with self.assertRaises(Exception):
            Player.objects.create(
                league=self.league,
                sportsconnect_player_id="SC-DUP",
                first_name="C",
                last_name="D",
            )

    def test_ordering(self):
        Player.objects.create(
            league=self.league,
            sportsconnect_player_id="SC-Z",
            first_name="Zoe",
            last_name="Anderson",
        )
        Player.objects.create(
            league=self.league,
            sportsconnect_player_id="SC-A",
            first_name="Aaron",
            last_name="Adams",
        )
        players = list(Player.objects.all())
        self.assertEqual(players[0].last_name, "Adams")


class PlayerSeasonModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league,
            name="Spring 2026",
            year=2026,
            season_type="spring",
            is_active=True,
        )
        self.division = Division.objects.create(league=self.league, name="Majors")
        self.player = Player.objects.create(
            league=self.league,
            sportsconnect_player_id="SC-100",
            first_name="Test",
            last_name="Player",
        )

    def test_create(self):
        ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.season,
            division=self.division,
        )
        self.assertEqual(ps.status, "registered")
        self.assertFalse(ps.is_protected)
        self.assertFalse(ps.is_top_4)

    def test_str(self):
        ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.season,
            division=self.division,
        )
        self.assertIn("Test Player", str(ps))
        self.assertIn("Spring 2026", str(ps))

    def test_unique_together_player_season(self):
        PlayerSeason.objects.create(
            player=self.player,
            season=self.season,
            division=self.division,
        )
        with self.assertRaises(Exception):
            PlayerSeason.objects.create(
                player=self.player,
                season=self.season,
                division=self.division,
            )

    def test_rsvp_token_auto_generated(self):
        ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.season,
        )
        self.assertIsNotNone(ps.rsvp_token)

    def test_checkin_token_auto_generated(self):
        ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.season,
        )
        self.assertIsNotNone(ps.checkin_token)


class TeamModelTests(TestCase):
    def setUp(self):
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league,
            name="Spring 2026",
            year=2026,
            season_type="spring",
        )
        self.division = Division.objects.create(league=self.league, name="Majors")

    def test_team_str(self):
        team = Team.objects.create(league=self.league, name="Marlins")
        self.assertEqual(str(team), "Marlins")

    def test_team_season_str(self):
        team = Team.objects.create(league=self.league, name="Dolphins")
        ts = TeamSeason.objects.create(
            team=team,
            season=self.season,
            division=self.division,
        )
        result = str(ts)
        self.assertIn("Dolphins", result)
        self.assertIn("Majors", result)

    def test_team_season_with_sub_league(self):
        team = Team.objects.create(league=self.league, name="Dolphins")
        ts = TeamSeason.objects.create(
            team=team,
            season=self.season,
            division=self.division,
            sub_league="American",
        )
        self.assertIn("American", str(ts))

    def test_team_season_unique_together(self):
        team = Team.objects.create(league=self.league, name="Marlins")
        TeamSeason.objects.create(
            team=team,
            season=self.season,
            division=self.division,
        )
        with self.assertRaises(Exception):
            TeamSeason.objects.create(
                team=team,
                season=self.season,
                division=self.division,
            )


class PlayerViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = _create_user()
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league,
            name="Spring 2026",
            year=2026,
            season_type="spring",
            is_active=True,
        )

    def test_index_requires_login(self):
        resp = self.client.get(reverse("players:index"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_index_authenticated(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(reverse("players:index"))
        self.assertEqual(resp.status_code, 200)

    def test_teams_requires_login(self):
        resp = self.client.get(reverse("players:teams"))
        self.assertEqual(resp.status_code, 302)

    def test_teams_authenticated(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(reverse("players:teams"))
        self.assertEqual(resp.status_code, 200)


class DugoutCardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = _create_user()
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league,
            name="Spring 2026",
            year=2026,
            season_type="spring",
            is_active=True,
        )
        self.division = Division.objects.create(league=self.league, name="Majors")
        self.team = Team.objects.create(league=self.league, name="Marlins")
        self.team_season = TeamSeason.objects.create(
            team=self.team,
            season=self.season,
            division=self.division,
        )
        self.player = Player.objects.create(
            league=self.league,
            sportsconnect_player_id="sc-1",
            first_name="Ada",
            last_name="Lovelace",
        )
        self.ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.season,
            division=self.division,
            assigned_team=self.team_season,
            account_name="Augusta Lovelace",
        )

    def test_dugout_card_requires_login(self):
        resp = self.client.get(
            reverse("players:dugout_card", args=[self.team_season.pk]),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_dugout_card_renders_for_valid_team(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:dugout_card", args=[self.team_season.pk]),
        )
        self.assertEqual(resp.status_code, 200)
        # Team strip header, roster row, guardian, schedule heading,
        # and the window.print() Print button are all on the card.
        self.assertContains(resp, "Marlins")
        self.assertContains(resp, "Ada Lovelace")
        self.assertContains(resp, "Augusta Lovelace")
        self.assertContains(resp, "Next 5 games")
        self.assertContains(resp, "window.print()")

    def test_dugout_card_404_for_missing_team(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:dugout_card", args=[9999]),
        )
        self.assertEqual(resp.status_code, 404)

    def test_dugout_card_renders_empty_roster(self):
        empty_team = Team.objects.create(league=self.league, name="Penguins")
        empty_ts = TeamSeason.objects.create(
            team=empty_team,
            season=self.season,
            division=self.division,
        )
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:dugout_card", args=[empty_ts.pk]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No players assigned")


# ---------------------------------------------------------------------------
# SFLL-114 — Print surfaces (Phase 9)
# ---------------------------------------------------------------------------


class PrintSurfaceTests(TestCase):
    """print_index + print_dugout_card views: login gates, rendering,
    coach / game / emergency-contact data, auto-print toggle."""

    def setUp(self):
        self.client = Client()
        self.user = _create_user()
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league,
            name="Spring 2026",
            year=2026,
            season_type="spring",
            is_active=True,
        )
        self.division = Division.objects.create(league=self.league, name="Majors")
        self.team = Team.objects.create(league=self.league, name="Giants")
        self.team_season = TeamSeason.objects.create(
            team=self.team,
            season=self.season,
            division=self.division,
        )
        self.player = Player.objects.create(
            league=self.league,
            sportsconnect_player_id="sc-p1",
            first_name="Babe",
            last_name="Ruth",
        )
        self.ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.season,
            division=self.division,
            assigned_team=self.team_season,
            account_name="George Ruth Sr",
            account_email="george.sr@example.com",
            additional_email="claire@example.com",
        )
        # Coach setup
        self.coach_user = User.objects.create_user(
            username="coach@sfll.org",
            email="coach@sfll.org",
            first_name="Casey",
            last_name="Stengel",
            password="coachpass",
        )
        self.coach = Coach.objects.create(
            user=self.coach_user,
            league=self.league,
            phone="415-555-0100",
        )
        self.coach_season = CoachSeason.objects.create(
            coach=self.coach,
            team_season=self.team_season,
            season=self.season,
            role="head_coach",
        )
        # Future session for game schedule
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.session = Session.objects.create(
            season=self.season,
            division=self.division,
            name="Opening Day",
            date=tomorrow,
            start_time="10:00",
            location="Kimbell Park Field 1",
        )

    # ── print_index ──────────────────────────────────────────────────────

    def test_print_index_requires_login(self):
        resp = self.client.get(reverse("players:print_index"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_print_index_lists_teams(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(reverse("players:print_index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Giants")
        self.assertContains(resp, "Print card")

    def test_print_index_no_active_season(self):
        self.season.is_active = False
        self.season.save()
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(reverse("players:print_index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No active season")

    # ── print_dugout_card ─────────────────────────────────────────────────

    def test_print_dugout_card_requires_login(self):
        resp = self.client.get(
            reverse("players:print_dugout_card", args=[self.team_season.pk]),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_print_dugout_card_renders_team_strip(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:print_dugout_card", args=[self.team_season.pk]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Giants")
        self.assertContains(resp, "Majors")
        self.assertContains(resp, "Spring 2026")

    def test_print_dugout_card_shows_head_coach(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:print_dugout_card", args=[self.team_season.pk]),
        )
        self.assertContains(resp, "Casey Stengel")
        self.assertContains(resp, "415-555-0100")

    def test_print_dugout_card_shows_roster_and_contacts(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:print_dugout_card", args=[self.team_season.pk]),
        )
        self.assertContains(resp, "Babe Ruth")
        self.assertContains(resp, "George Ruth Sr")
        self.assertContains(resp, "george.sr@example.com")
        self.assertContains(resp, "claire@example.com")

    def test_print_dugout_card_shows_schedule(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:print_dugout_card", args=[self.team_season.pk]),
        )
        self.assertContains(resp, "Opening Day")
        self.assertContains(resp, "Kimbell Park Field 1")

    def test_print_dugout_card_auto_print_on_by_default(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:print_dugout_card", args=[self.team_season.pk]),
        )
        # The on-load script is emitted; the toolbar "Print again" button
        # is always present regardless of the ?print flag.
        self.assertContains(resp, "window.addEventListener")

    def test_print_dugout_card_auto_print_suppressed(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:print_dugout_card", args=[self.team_season.pk]),
            {"print": "0"},
        )
        self.assertNotContains(resp, "window.addEventListener")

    def test_print_dugout_card_404_for_missing_team(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:print_dugout_card", args=[9999]),
        )
        self.assertEqual(resp.status_code, 404)

    def test_print_css_no_forced_page_break_on_dugout_card(self):
        import os

        css_path = os.path.normpath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "static",
                "css",
                "lms-print.css",
            )
        )
        with open(css_path) as f:
            css = f.read()
        # Both half-sheet cards must stay on one letter page. A forced
        # break-after on .dugout-card would push them onto separate pages.
        self.assertNotIn(
            "break-after: page",
            css,
            "lms-print.css must not force break-after: page on .dugout-card "
            "(splits the two half-sheet cards onto separate pages)",
        )
        self.assertNotIn(
            "page-break-after: always",
            css,
            "lms-print.css must not use page-break-after: always on .dugout-card",
        )

    def test_print_dugout_card_empty_roster(self):
        empty_team = Team.objects.create(league=self.league, name="Cubs")
        empty_ts = TeamSeason.objects.create(
            team=empty_team,
            season=self.season,
            division=self.division,
        )
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:print_dugout_card", args=[empty_ts.pk]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No players assigned")

    def test_print_dugout_card_session_filter_excludes_other_season(self):
        """Sessions from a different season sharing the same division must not appear."""
        from tryouts.models import Session as TryoutSession
        import datetime
        # Session in this division but a DIFFERENT season
        other_season = Season.objects.create(
            league=self.league, name="Fall 2026", year=2026,
            season_type="fall", is_active=False,
        )
        TryoutSession.objects.create(
            season=other_season,
            division=self.division,
            name="Fall Session",
            date=datetime.date.today() + datetime.timedelta(days=1),
            start_time=datetime.time(9, 0),
        )
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:print_dugout_card", args=[self.team_season.pk]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Fall Session")


# ---------------------------------------------------------------------------
# SFLL-95 — Family Detail (Phase 4)
# ---------------------------------------------------------------------------

FAMILY_EMAIL = "rodriguez.family@example.com"
OTHER_FAMILY_EMAIL = "other@example.com"


class FamilyDetailTests(TestCase):
    """Family Detail page: groups PlayerSeasons by account_email and surfaces
    players, contacts, balance shell, volunteer shell, and comms history."""

    def setUp(self):
        self.client = Client()
        self.user = _create_user()
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league,
            name="Spring 2026",
            year=2026,
            season_type="spring",
            is_active=True,
        )
        self.division = Division.objects.create(league=self.league, name="Majors")

        self.player1 = Player.objects.create(
            league=self.league,
            sportsconnect_player_id="SC-FAM-1",
            first_name="Jayden",
            last_name="Rodriguez",
        )
        self.player2 = Player.objects.create(
            league=self.league,
            sportsconnect_player_id="SC-FAM-2",
            first_name="Alex",
            last_name="Rodriguez",
        )
        self.ps1 = PlayerSeason.objects.create(
            player=self.player1,
            season=self.season,
            division=self.division,
            account_name="Maria Rodriguez",
            account_email=FAMILY_EMAIL,
            additional_email="papa@example.com",
        )
        self.ps2 = PlayerSeason.objects.create(
            player=self.player2,
            season=self.season,
            division=self.division,
            account_name="Maria Rodriguez",
            account_email=FAMILY_EMAIL,
        )
        # An unrelated player on a different account.
        other_player = Player.objects.create(
            league=self.league,
            sportsconnect_player_id="SC-OTHER",
            first_name="Other",
            last_name="Kid",
        )
        PlayerSeason.objects.create(
            player=other_player,
            season=self.season,
            division=self.division,
            account_name="Other Parent",
            account_email=OTHER_FAMILY_EMAIL,
        )

        self.family_key = encode_family_key(FAMILY_EMAIL)

    def _give_player_agent_role(self):
        UserRole.objects.create(user=self.user, league=self.league, role='player_agent')

    # ----- index -----

    def test_family_index_requires_login(self):
        resp = self.client.get(reverse("players:family_index"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_family_index_requires_staff_role(self):
        # Logged-in user without a staff role must be denied.
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:family_index'))
        self.assertEqual(resp.status_code, 403)

    def test_family_index_rejects_role_in_other_league(self):
        # SFLL-146: a role in a different league must NOT grant access to
        # this season's family list (cross-league IDOR regression test).
        other_league = League.objects.create(name='Other League', short_name='OL')
        UserRole.objects.create(user=self.user, league=other_league, role='player_agent')
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:family_index'))
        self.assertEqual(resp.status_code, 403)

    def test_family_index_lists_families(self):
        self._give_player_agent_role()
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:family_index'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Maria Rodriguez")
        self.assertContains(resp, FAMILY_EMAIL)
        self.assertContains(resp, "Other Parent")

    def test_family_index_no_active_season(self):
        self.season.is_active = False
        self.season.save()
        self._give_player_agent_role()
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(reverse('players:family_index'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No active season")

    # ----- detail -----

    def test_family_detail_requires_login(self):
        resp = self.client.get(
            reverse("players:family_detail", args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_family_detail_requires_staff_role(self):
        # Logged-in user without a staff role must be denied.
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse('players:family_detail', args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 403)

    def test_family_detail_renders(self):
        self._give_player_agent_role()
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse("players:family_detail", args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        # Header pulls account name + sibling count.
        self.assertContains(resp, "Maria Rodriguez")
        self.assertContains(resp, "2 players")
        # Both siblings appear.
        self.assertContains(resp, "Jayden Rodriguez")
        self.assertContains(resp, "Alex Rodriguez")
        # Other family isn't accidentally pulled in.
        self.assertNotContains(resp, "Other Kid")
        # Contacts grid shows primary + secondary; emergency is a placeholder.
        self.assertContains(resp, "Primary parent")
        self.assertContains(resp, "Secondary contact")
        self.assertContains(resp, "Emergency contact")
        self.assertContains(resp, "papa@example.com")
        # Volunteer shell and division context.
        self.assertContains(resp, "Volunteer obligations")
        self.assertContains(resp, "Majors")
        # Comms shell renders even with no email logs.
        self.assertContains(resp, "Recent communications")

    def test_family_detail_404_for_unknown_family(self):
        self._give_player_agent_role()
        self.client.login(username='test@sfll.org', password='testpass123')
        bogus = encode_family_key('nobody@example.com')
        resp = self.client.get(
            reverse("players:family_detail", args=[bogus]),
        )
        self.assertEqual(resp.status_code, 404)

    def test_family_detail_404_for_malformed_key(self):
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:family_detail", args=["not-a-valid-key!!!"]),
        )
        self.assertEqual(resp.status_code, 404)

    def test_family_detail_404_when_no_active_season(self):
        self.season.is_active = False
        self.season.save()
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:family_detail", args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 404)

    def test_family_detail_includes_comms_history(self):
        EmailLog.objects.create(
            player_season=self.ps1,
            to_address=FAMILY_EMAIL,
            subject="SES reminder for Jayden",
            body_snapshot="You have an SES session tomorrow.",
        )
        EmailLog.objects.create(
            player_season=self.ps2,
            to_address=FAMILY_EMAIL,
            subject="SES reminder for Alex",
            body_snapshot="You have an SES session tomorrow.",
        )
        self._give_player_agent_role()
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse("players:family_detail", args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "SES reminder for Jayden")
        self.assertContains(resp, "SES reminder for Alex")

    # ----- treasurer + balance gating -----

    def test_balance_section_hidden_for_regular_user(self):
        # Plain logged-in user (no staff role) is denied access entirely.
        self.client.login(username='test@sfll.org', password='testpass123')
        resp = self.client.get(
            reverse("players:family_detail", args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 403)

    def test_treasurer_sees_balance_in_readonly_mode(self):
        UserRole.objects.create(
            user=self.user,
            league=self.league,
            role="treasurer",
        )
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:family_detail", args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Balance")
        self.assertContains(resp, "Treasurer view")
        self.assertContains(resp, "read-only")

    def test_admin_sees_balance_without_readonly_badge(self):
        UserRole.objects.create(
            user=self.user,
            league=self.league,
            role="cto",
        )
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:family_detail", args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Balance")
        self.assertNotContains(resp, "Treasurer view")

    def test_treasurer_plus_admin_loses_readonly_badge(self):
        # Multi-role: someone with both treasurer and admin caps shouldn't be
        # locked into the read-only view.
        UserRole.objects.create(
            user=self.user,
            league=self.league,
            role="treasurer",
        )
        UserRole.objects.create(
            user=self.user,
            league=self.league,
            role="president",
        )
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:family_detail", args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Balance")
        self.assertNotContains(resp, "Treasurer view")

    def test_balance_hidden_for_role_in_other_league(self):
        # Roles on a *different* League must not grant access at all.
        other_league = League.objects.create(
            name="Oakland Little League",
            short_name="OLL",
        )
        UserRole.objects.create(
            user=self.user,
            league=other_league,
            role="treasurer",
        )
        UserRole.objects.create(
            user=self.user,
            league=other_league,
            role="president",
        )
        self.client.login(username="test@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("players:family_detail", args=[self.family_key]),
        )
        self.assertEqual(resp.status_code, 403)


class RosterFilterTests(TestCase):
    """Roster (SFLL-108) — querystring filters: q, division, league, view."""

    def setUp(self):
        self.client = Client()
        _create_user()
        self.client.login(username="test@sfll.org", password="testpass123")
        self.league = _create_league()
        self.season = Season.objects.create(
            league=self.league,
            name="Spring 2026",
            year=2026,
            season_type="spring",
            is_active=True,
        )
        self.majors = Division.objects.create(
            league=self.league,
            name="Majors",
            display_order=0,
            has_leagues=True,
            league_names=["American", "National"],
        )
        self.aaa = Division.objects.create(
            league=self.league,
            name="AAA",
            display_order=1,
        )
        team = Team.objects.create(league=self.league, name="Marlins")
        self.team_american = TeamSeason.objects.create(
            team=team,
            season=self.season,
            division=self.majors,
            sub_league="American",
        )
        self.alpha = self._player(
            "SC-A",
            "Alpha",
            "Adams",
            division=self.majors,
            team=self.team_american,
            top4=True,
        )
        self.bravo = self._player("SC-B", "Bravo", "Brown", division=self.majors)
        self.charlie = self._player("SC-C", "Charlie", "Clark", division=self.aaa)

    def _player(self, sc_id, first, last, division=None, team=None, top4=False):
        p = Player.objects.create(
            league=self.league,
            sportsconnect_player_id=sc_id,
            first_name=first,
            last_name=last,
        )
        return PlayerSeason.objects.create(
            player=p,
            season=self.season,
            division=division,
            assigned_team=team,
            is_top_4=top4,
        )

    def test_search_matches_last_name(self):
        resp = self.client.get(reverse("players:index"), {"q": "Brown"})
        self.assertEqual(resp.status_code, 200)
        items = list(resp.context["player_seasons"])
        self.assertEqual(items, [self.bravo])

    def test_division_filter(self):
        resp = self.client.get(reverse("players:index"), {"division": str(self.aaa.id)})
        items = list(resp.context["player_seasons"])
        self.assertEqual(items, [self.charlie])
        self.assertEqual(resp.context["selected_division"], self.aaa)

    def test_unassigned_view_excludes_assigned(self):
        resp = self.client.get(reverse("players:index"), {"view": "unassigned"})
        items = list(resp.context["player_seasons"])
        self.assertIn(self.bravo, items)
        self.assertIn(self.charlie, items)
        self.assertNotIn(self.alpha, items)

    def test_top4_view(self):
        resp = self.client.get(reverse("players:index"), {"view": "top4"})
        items = list(resp.context["player_seasons"])
        self.assertEqual(items, [self.alpha])

    def test_sub_league_only_active_for_multi_league_division(self):
        resp = self.client.get(
            reverse("players:index"),
            {"division": str(self.majors.id), "league": "American"},
        )
        items = list(resp.context["player_seasons"])
        self.assertEqual(items, [self.alpha])
        self.assertEqual(resp.context["sub_leagues"], ["American", "National"])

    def test_sub_leagues_empty_for_single_league_division(self):
        resp = self.client.get(reverse("players:index"), {"division": str(self.aaa.id)})
        self.assertEqual(resp.context["sub_leagues"], [])

    def test_search_preserves_active_filters(self):
        # Regression: form submit must not drop active division/view filters.
        # Template hidden inputs make this work; this test catches regressions.
        resp = self.client.get(
            reverse("players:index"),
            {
                "q": "Adams",
                "division": str(self.majors.id),
                "view": "top4",
            },
        )
        self.assertEqual(resp.status_code, 200)
        items = list(resp.context["player_seasons"])
        self.assertEqual(items, [self.alpha])
        content = resp.content.decode()
        self.assertIn(f'name="division" value="{self.majors.id}"', content)
        self.assertIn('name="view" value="top4"', content)


class PrintCSSRegressionTest(SimpleTestCase):
    """Regression tests for SFLL-129: two dugout cards must share one letter sheet."""

    @staticmethod
    def _read_css(filename):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, 'static', 'css', filename)
        with open(path) as f:
            return f.read()

    def _assert_no_forced_break(self, css, filename):
        self.assertNotIn(
            'page-break-after: always',
            css,
            f'{filename} must not force a page break after each .dugout-card',
        )
        self.assertNotIn(
            'break-after: page',
            css,
            f'{filename} must not force a page break after each .dugout-card',
        )

    def test_lms_print_css_no_forced_page_break_on_dugout_card(self):
        self._assert_no_forced_break(self._read_css('lms-print.css'), 'lms-print.css')

    def test_lms_components_css_no_forced_page_break_on_dugout_card(self):
        self._assert_no_forced_break(self._read_css('lms-components.css'), 'lms-components.css')
