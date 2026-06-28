"""Tests for the draft app — DraftSession, DraftPick models and views."""

import json
from datetime import date, time

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Coach, CoachSeason, User, UserRole
from draft.models import DraftPick, DraftSession
from evaluations.models import CoachRanking
from players.models import (
    Division,
    League,
    Player,
    PlayerSeason,
    Season,
    Team,
    TeamSeason,
)


def _setup_draft_base():
    """Full object graph for draft tests."""
    league = League.objects.create(name="SFLL", short_name="SFLL")
    season = Season.objects.create(
        league=league,
        name="Spring 2026",
        year=2026,
        season_type="spring",
        is_active=True,
    )
    division = Division.objects.create(league=league, name="Majors", display_order=0)

    # Two teams
    team1 = Team.objects.create(league=league, name="Marlins")
    team2 = Team.objects.create(league=league, name="Dolphins")
    ts1 = TeamSeason.objects.create(team=team1, season=season, division=division)
    ts2 = TeamSeason.objects.create(team=team2, season=season, division=division)

    # Coach (head_coach, drafter for team1)
    coach_user = User.objects.create_user(
        username="hc@sfll.org",
        email="hc@sfll.org",
        first_name="Head",
        last_name="Coach",
        password="testpass123",
    )
    coach = Coach.objects.create(user=coach_user, league=league)
    coach_season = CoachSeason.objects.create(
        coach=coach,
        team_season=ts1,
        season=season,
        role="head_coach",
        is_drafter=True,
    )
    ts1.drafter = coach_season
    ts1.save()

    # Players
    players = []
    player_seasons = []
    for i in range(1, 9):
        p = Player.objects.create(
            league=league,
            sportsconnect_player_id=f"SC-{i:03d}",
            first_name=f"Player{i}",
            last_name=f"Last{i}",
        )
        ps = PlayerSeason.objects.create(
            player=p,
            season=season,
            division=division,
        )
        players.append(p)
        player_seasons.append(ps)

    return {
        "league": league,
        "season": season,
        "division": division,
        "team1": team1,
        "team2": team2,
        "ts1": ts1,
        "ts2": ts2,
        "coach_user": coach_user,
        "coach": coach,
        "coach_season": coach_season,
        "players": players,
        "player_seasons": player_seasons,
    }


class DraftSessionModelTests(TestCase):
    def setUp(self):
        self.d = _setup_draft_base()

    def test_create(self):
        ds = DraftSession.objects.create(
            season=self.d["season"],
            division=self.d["division"],
        )
        self.assertEqual(ds.status, "pending")
        self.assertTrue(ds.snake_draft)
        self.assertEqual(ds.current_round, 1)
        self.assertEqual(ds.current_pick, 1)

    def test_str(self):
        ds = DraftSession.objects.create(
            season=self.d["season"],
            division=self.d["division"],
        )
        self.assertIn("Majors", str(ds))
        self.assertIn("Draft", str(ds))

    def test_str_with_sub_league(self):
        ds = DraftSession.objects.create(
            season=self.d["season"],
            division=self.d["division"],
            sub_league="American",
        )
        self.assertIn("American", str(ds))


class DraftPickModelTests(TestCase):
    def setUp(self):
        self.d = _setup_draft_base()
        self.ds = DraftSession.objects.create(
            season=self.d["season"],
            division=self.d["division"],
        )

    def test_create(self):
        pick = DraftPick.objects.create(
            draft_session=self.ds,
            team_season=self.d["ts1"],
            player_season=self.d["player_seasons"][0],
            round_number=1,
            pick_number=1,
        )
        self.assertEqual(pick.round_number, 1)
        self.assertFalse(pick.is_top_4)
        self.assertFalse(pick.is_coaches_child)

    def test_str(self):
        pick = DraftPick.objects.create(
            draft_session=self.ds,
            team_season=self.d["ts1"],
            player_season=self.d["player_seasons"][0],
            round_number=1,
            pick_number=1,
        )
        result = str(pick)
        self.assertIn("R1 P1", result)
        self.assertIn("Player1", result)
        self.assertIn("Marlins", result)

    def test_unique_together_draft_session_pick(self):
        DraftPick.objects.create(
            draft_session=self.ds,
            team_season=self.d["ts1"],
            player_season=self.d["player_seasons"][0],
            round_number=1,
            pick_number=1,
        )
        with self.assertRaises(Exception):
            DraftPick.objects.create(
                draft_session=self.ds,
                team_season=self.d["ts2"],
                player_season=self.d["player_seasons"][1],
                round_number=1,
                pick_number=1,
            )

    def test_ordering_by_pick_number(self):
        DraftPick.objects.create(
            draft_session=self.ds,
            team_season=self.d["ts2"],
            player_season=self.d["player_seasons"][1],
            round_number=1,
            pick_number=2,
        )
        DraftPick.objects.create(
            draft_session=self.ds,
            team_season=self.d["ts1"],
            player_season=self.d["player_seasons"][0],
            round_number=1,
            pick_number=1,
        )
        picks = list(DraftPick.objects.filter(draft_session=self.ds))
        self.assertEqual(picks[0].pick_number, 1)
        self.assertEqual(picks[1].pick_number, 2)


class DraftViewPermissionTests(TestCase):
    def setUp(self):
        self.d = _setup_draft_base()
        self.client = Client()

    def test_draft_home_requires_login(self):
        resp = self.client.get(reverse("draft:index"))
        self.assertEqual(resp.status_code, 302)

    def test_draft_home_authenticated(self):
        self.client.login(username="hc@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:index"))
        self.assertEqual(resp.status_code, 200)


class CoachRankingsViewTests(TestCase):
    def setUp(self):
        self.d = _setup_draft_base()
        self.client = Client()

    def test_rankings_requires_head_coach(self):
        """Assistant coach should be forbidden."""
        user2 = User.objects.create_user(
            username="ac@sfll.org",
            email="ac@sfll.org",
            first_name="Asst",
            last_name="Coach",
            password="testpass123",
        )
        coach2 = Coach.objects.create(user=user2, league=self.d["league"])
        CoachSeason.objects.create(
            coach=coach2,
            team_season=self.d["ts2"],
            season=self.d["season"],
            role="assistant_coach",
        )
        self.client.login(username="ac@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:rankings"))
        self.assertEqual(resp.status_code, 403)

    def test_rankings_allowed_for_head_coach(self):
        self.client.login(username="hc@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:rankings"))
        self.assertEqual(resp.status_code, 200)

    def test_save_rankings_post(self):
        self.client.login(username="hc@sfll.org", password="testpass123")
        ps_ids = [ps.pk for ps in self.d["player_seasons"][:4]]
        resp = self.client.post(
            reverse("draft:save_rankings"),
            data=json.dumps({"ranked_ids": ps_ids}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 4)
        self.assertEqual(
            CoachRanking.objects.filter(coach_season=self.d["coach_season"]).count(), 4
        )

    def test_save_rankings_replaces_existing(self):
        self.client.login(username="hc@sfll.org", password="testpass123")
        ps_ids = [ps.pk for ps in self.d["player_seasons"][:3]]
        self.client.post(
            reverse("draft:save_rankings"),
            data=json.dumps({"ranked_ids": ps_ids}),
            content_type="application/json",
        )
        # Now save a different set
        ps_ids2 = [ps.pk for ps in self.d["player_seasons"][3:6]]
        self.client.post(
            reverse("draft:save_rankings"),
            data=json.dumps({"ranked_ids": ps_ids2}),
            content_type="application/json",
        )
        # Should have exactly 3 (replaced, not appended)
        self.assertEqual(
            CoachRanking.objects.filter(coach_season=self.d["coach_season"]).count(), 3
        )


class SeedingViewTests(TestCase):
    def setUp(self):
        self.d = _setup_draft_base()
        self.client = Client()
        # Create a CTO user
        self.cto = User.objects.create_user(
            username="cto@sfll.org",
            email="cto@sfll.org",
            first_name="CTO",
            last_name="Admin",
            password="testpass123",
            is_superuser=True,
        )

    def test_seeding_forbidden_for_regular_user(self):
        user = User.objects.create_user(
            username="nobody@sfll.org",
            email="nobody@sfll.org",
            first_name="No",
            last_name="Body",
            password="testpass123",
        )
        self.client.login(username="nobody@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:seeding", args=[self.d["division"].pk]))
        self.assertEqual(resp.status_code, 403)

    def test_seeding_allowed_for_superuser(self):
        self.client.login(username="cto@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:seeding", args=[self.d["division"].pk]))
        self.assertEqual(resp.status_code, 200)

    def test_save_seeding_creates_draft_session_and_picks(self):
        self.client.login(username="cto@sfll.org", password="testpass123")
        assignments = {
            str(self.d["ts1"].pk): [
                self.d["player_seasons"][0].pk,
                self.d["player_seasons"][1].pk,
            ],
            str(self.d["ts2"].pk): [
                self.d["player_seasons"][2].pk,
                self.d["player_seasons"][3].pk,
            ],
        }
        resp = self.client.post(
            reverse("draft:save_seeding", args=[self.d["division"].pk]),
            data=json.dumps({"assignments": assignments}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["total_assigned"], 4)

        # Verify DraftPick records
        ds = DraftSession.objects.get(
            season=self.d["season"],
            division=self.d["division"],
        )
        self.assertEqual(
            DraftPick.objects.filter(draft_session=ds, is_top_4=True).count(), 4
        )

    def test_lock_seeding(self):
        self.client.login(username="cto@sfll.org", password="testpass123")
        # First save some seeding
        ds = DraftSession.objects.create(
            season=self.d["season"],
            division=self.d["division"],
            status="pending",
        )
        DraftPick.objects.create(
            draft_session=ds,
            team_season=self.d["ts1"],
            player_season=self.d["player_seasons"][0],
            round_number=0,
            pick_number=1,
            is_top_4=True,
            picked_by=self.cto,
        )
        resp = self.client.post(
            reverse("draft:lock_seeding", args=[self.d["division"].pk]),
        )
        self.assertEqual(resp.status_code, 200)
        ds.refresh_from_db()
        self.assertEqual(ds.status, "seeding")

    def test_lock_seeding_idempotent_rejects(self):
        """Locking when already locked should return error."""
        self.client.login(username="cto@sfll.org", password="testpass123")
        ds = DraftSession.objects.create(
            season=self.d["season"],
            division=self.d["division"],
            status="seeding",
        )
        resp = self.client.post(
            reverse("draft:lock_seeding", args=[self.d["division"].pk]),
        )
        self.assertEqual(resp.status_code, 400)


class DraftBoardViewTests(TestCase):
    """Phase 7: live draft board renders on Pacific tokens."""

    def setUp(self):
        self.d = _setup_draft_base()
        self.client = Client()
        self.ds = DraftSession.objects.create(
            season=self.d["season"],
            division=self.d["division"],
            status="drafting",
            current_round=1,
            current_pick=1,
            team_order=[self.d["ts1"].pk, self.d["ts2"].pk],
            started_at=timezone.now(),
        )

    def test_draft_board_renders_for_head_coach(self):
        self.client.login(username="hc@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:draft_board", args=[self.ds.pk]))
        self.assertEqual(resp.status_code, 200)
        # Pacific shell markers — would be missing if we regressed to dark Tailwind.
        self.assertContains(resp, 'class="page page--wide"')
        self.assertContains(resp, "draft-shell")
        self.assertContains(resp, "draft-grid")
        self.assertContains(resp, "queue")

    def test_draft_board_renders_top_4_row_when_seeded(self):
        DraftPick.objects.create(
            draft_session=self.ds,
            team_season=self.d["ts1"],
            player_season=self.d["player_seasons"][0],
            round_number=0,
            pick_number=1,
            is_top_4=True,
            is_coaches_child=True,
            picked_by=self.d["coach_user"],
        )
        self.client.login(username="hc@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:draft_board", args=[self.ds.pk]))
        self.assertEqual(resp.status_code, 200)
        # is_top_4 + is_coaches_child both flow into picks_json, where the
        # template/Alpine drive Seed and CC marker rendering.
        self.assertContains(resp, '"is_top_4": true')
        self.assertContains(resp, '"is_coaches_child": true')

    def test_draft_board_drops_legacy_tailwind_chrome(self):
        """SFLL-112 acceptance — no dark Tailwind classes from the legacy template.

        If we regress to bg-gray-800 / rounded-xl / text-emerald-400 / etc.
        on the rebuilt draft board, this test fails. Phase 2 components
        (`card`, `pill`, `btn`, etc.) plus the Phase-7-specific draft-grid
        primitives carry the look now.
        """
        self.client.login(username="hc@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:draft_board", args=[self.ds.pk]))
        body = resp.content.decode()
        for legacy in (
            "bg-gray-800",
            "bg-gray-700",
            "text-emerald-400",
            "rounded-xl",
            "border-gray-700",
            "bg-emerald-900",
            "json|safe",
        ):
            self.assertNotIn(
                legacy,
                body,
                f"Legacy pattern `{legacy}` leaked back into the draft board.",
            )


class DraftRoomViewTests(TestCase):
    """SFLL-115 — iPad Draft Room split-pane."""

    def setUp(self):
        self.d = _setup_draft_base()
        self.ds = DraftSession.objects.create(
            season=self.d["season"],
            division=self.d["division"],
            status="drafting",
            current_round=1,
            current_pick=1,
            team_order=[self.d["ts1"].pk, self.d["ts2"].pk],
        )
        UserRole.objects.create(
            user=self.d["coach_user"],
            league=self.d["league"],
            role="cto",
            is_active=True,
        )
        self.client = Client()

    def test_draft_room_renders(self):
        self.client.login(username="hc@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:draft_room", args=[self.ds.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "draft-room")
        self.assertContains(resp, "On the clock")
        self.assertContains(resp, "On deck")
        self.assertContains(resp, self.d["division"].name)

    def test_draft_room_lists_available_players(self):
        self.client.login(username="hc@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:draft_room", args=[self.ds.pk]))
        for ps in self.d["player_seasons"]:
            self.assertContains(resp, ps.player.full_name)

    def test_draft_room_excludes_drafted_players(self):
        import json as _json
        import re as _re

        DraftPick.objects.create(
            draft_session=self.ds,
            team_season=self.d["ts1"],
            player_season=self.d["player_seasons"][0],
            round_number=1,
            pick_number=1,
            is_top_4=False,
            picked_by=self.d["coach_user"],
        )
        self.client.login(username="hc@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:draft_room", args=[self.ds.pk]))
        drafted_ps = self.d["player_seasons"][0]
        body = resp.content.decode()
        picks_match = _re.search(
            r'<script[^>]+id="picks-data"[^>]*>(.*?)</script>', body, _re.DOTALL
        )
        available_match = _re.search(
            r'<script[^>]+id="available-data"[^>]*>(.*?)</script>', body, _re.DOTALL
        )
        picks_data = _json.loads(picks_match.group(1)) if picks_match else []
        available_data = (
            _json.loads(available_match.group(1)) if available_match else []
        )
        pick_player_ids = [p["player_id"] for p in picks_data]
        available_ids = [p["id"] for p in available_data]
        self.assertIn(drafted_ps.pk, pick_player_ids)
        self.assertNotIn(drafted_ps.pk, available_ids)

    def test_draft_room_404_for_missing_session(self):
        self.client.login(username="hc@sfll.org", password="testpass123")
        resp = self.client.get(reverse("draft:draft_room", args=[99999]))
        self.assertEqual(resp.status_code, 404)
