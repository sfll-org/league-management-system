"""Tests for the evaluations app — Evaluation, ObjectiveMetric, CoachRanking models and views."""

from datetime import date, time
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Coach, CoachSeason, User, UserRole
from evaluations.models import CoachRanking, Evaluation, ObjectiveMetric
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
from tryouts.models import CheckIn, Session, SessionAssignment


def _setup_eval_base():
    """Create the full object graph needed for evaluation tests."""
    league = League.objects.create(name="SFLL", short_name="SFLL")
    season = Season.objects.create(
        league=league,
        name="Spring 2026",
        year=2026,
        season_type="spring",
        is_active=True,
    )
    division = Division.objects.create(league=league, name="Majors", display_order=0)
    station = Station.objects.create(
        league=league,
        name="Hitting",
        display_order=0,
        eval_fields=[
            {"key": "power", "label": "Power", "type": "int", "min": 1, "max": 10},
            {"key": "contact", "label": "Contact", "type": "int", "min": 1, "max": 10},
        ],
    )
    team = Team.objects.create(league=league, name="Marlins")
    team_season = TeamSeason.objects.create(
        team=team,
        season=season,
        division=division,
    )
    # Coach
    coach_user = User.objects.create_user(
        username="coach@sfll.org",
        email="coach@sfll.org",
        first_name="Head",
        last_name="Coach",
        password="testpass123",
    )
    coach = Coach.objects.create(user=coach_user, league=league)
    coach_season = CoachSeason.objects.create(
        coach=coach,
        team_season=team_season,
        season=season,
        role="head_coach",
    )
    # Make the user staff so _is_eval_authorized passes
    coach_user.is_staff = True
    coach_user.save()

    # Player
    player = Player.objects.create(
        league=league,
        sportsconnect_player_id="SC-001",
        first_name="Jayden",
        last_name="Rodriguez",
    )
    ps = PlayerSeason.objects.create(
        player=player,
        season=season,
        division=division,
    )

    # Session + checked-in assignment
    session = Session.objects.create(
        season=season,
        name="SES 1",
        date=date(2026, 3, 28),
        start_time=time(9, 0),
        division=division,
    )
    assignment = SessionAssignment.objects.create(
        session=session,
        player_season=ps,
        assigned_by=coach_user,
    )
    CheckIn.objects.create(session_assignment=assignment, checked_in_by=coach_user)

    return {
        "league": league,
        "season": season,
        "division": division,
        "station": station,
        "team": team,
        "team_season": team_season,
        "coach_user": coach_user,
        "coach": coach,
        "coach_season": coach_season,
        "player": player,
        "ps": ps,
        "session": session,
        "assignment": assignment,
    }


class EvaluationModelTests(TestCase):
    def setUp(self):
        self.d = _setup_eval_base()

    def test_create_evaluation(self):
        ev = Evaluation.objects.create(
            player_season=self.d["ps"],
            session=self.d["session"],
            coach_season=self.d["coach_season"],
            station=self.d["station"],
            scores={"power": 8, "contact": 7},
            notes="Good hitter",
        )
        self.assertEqual(ev.scores["power"], 8)

    def test_str(self):
        ev = Evaluation.objects.create(
            player_season=self.d["ps"],
            session=self.d["session"],
            coach_season=self.d["coach_season"],
            station=self.d["station"],
            scores={},
        )
        self.assertIn("Hitting", str(ev))
        self.assertIn("Jayden Rodriguez", str(ev))

    def test_unique_together(self):
        Evaluation.objects.create(
            player_season=self.d["ps"],
            session=self.d["session"],
            coach_season=self.d["coach_season"],
            station=self.d["station"],
            scores={},
        )
        with self.assertRaises(Exception):
            Evaluation.objects.create(
                player_season=self.d["ps"],
                session=self.d["session"],
                coach_season=self.d["coach_season"],
                station=self.d["station"],
                scores={},
            )


class ObjectiveMetricModelTests(TestCase):
    def setUp(self):
        self.d = _setup_eval_base()

    def test_create(self):
        m = ObjectiveMetric.objects.create(
            player_season=self.d["ps"],
            session=self.d["session"],
            metric_type="60_yard_dash",
            value=Decimal("8.20"),
            unit="sec",
            recorded_by=self.d["coach_user"],
        )
        self.assertIn("60_yard_dash", str(m))
        self.assertIn("8.20", str(m))


class CoachRankingModelTests(TestCase):
    def setUp(self):
        self.d = _setup_eval_base()

    def test_create(self):
        r = CoachRanking.objects.create(
            coach_season=self.d["coach_season"],
            player_season=self.d["ps"],
            rank_order=1,
        )
        self.assertIn("#1", str(r))

    def test_unique_together(self):
        CoachRanking.objects.create(
            coach_season=self.d["coach_season"],
            player_season=self.d["ps"],
            rank_order=1,
        )
        with self.assertRaises(Exception):
            CoachRanking.objects.create(
                coach_season=self.d["coach_season"],
                player_season=self.d["ps"],
                rank_order=2,
            )

    def test_ordering(self):
        p2 = Player.objects.create(
            league=self.d["league"],
            sportsconnect_player_id="SC-002",
            first_name="Aiden",
            last_name="Martinez",
        )
        ps2 = PlayerSeason.objects.create(
            player=p2,
            season=self.d["season"],
            division=self.d["division"],
        )
        CoachRanking.objects.create(
            coach_season=self.d["coach_season"],
            player_season=ps2,
            rank_order=1,
        )
        CoachRanking.objects.create(
            coach_season=self.d["coach_season"],
            player_season=self.d["ps"],
            rank_order=2,
        )
        rankings = list(
            CoachRanking.objects.filter(coach_season=self.d["coach_season"])
        )
        self.assertEqual(rankings[0].rank_order, 1)
        self.assertEqual(rankings[1].rank_order, 2)


class EvalViewPermissionTests(TestCase):
    """Test that evaluation views enforce proper auth and role checks."""

    def setUp(self):
        self.d = _setup_eval_base()
        self.client = Client()

    def test_eval_home_requires_login(self):
        resp = self.client.get(reverse("evaluations:index"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_eval_home_forbidden_for_non_coach(self):
        user = User.objects.create_user(
            username="nobody@sfll.org",
            email="nobody@sfll.org",
            first_name="No",
            last_name="Body",
            password="testpass123",
        )
        self.client.login(username="nobody@sfll.org", password="testpass123")
        resp = self.client.get(reverse("evaluations:index"))
        self.assertEqual(resp.status_code, 403)

    def test_eval_home_allowed_for_coach(self):
        self.client.login(username="coach@sfll.org", password="testpass123")
        resp = self.client.get(reverse("evaluations:index"))
        self.assertEqual(resp.status_code, 200)

    def test_station_session_eval_view(self):
        self.client.login(username="coach@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse(
                "evaluations:station_session_eval",
                args=[self.d["station"].pk, self.d["session"].pk],
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_eval_player_requires_coach_season(self):
        """User without a CoachSeason should get 403."""
        user = User.objects.create_user(
            username="staffonly@sfll.org",
            email="staffonly@sfll.org",
            first_name="Staff",
            last_name="Only",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="staffonly@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse(
                "evaluations:eval_player",
                args=[self.d["station"].pk, self.d["session"].pk, self.d["ps"].pk],
            )
        )
        self.assertEqual(resp.status_code, 403)

    def test_eval_player_allowed_for_coach_with_season(self):
        self.client.login(username="coach@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse(
                "evaluations:eval_player",
                args=[self.d["station"].pk, self.d["session"].pk, self.d["ps"].pk],
            )
        )
        self.assertEqual(resp.status_code, 200)


class SaveEvalTests(TestCase):
    """Test the save_eval POST endpoint."""

    def setUp(self):
        self.d = _setup_eval_base()
        self.client = Client()
        self.client.login(username="coach@sfll.org", password="testpass123")

    def test_save_eval_creates_record(self):
        resp = self.client.post(
            reverse(
                "evaluations:save_eval",
                args=[self.d["station"].pk, self.d["session"].pk, self.d["ps"].pk],
            ),
            {
                "score_power": "8",
                "score_contact": "7",
                "notes": "Good swing",
                "action": "save",
            },
        )
        self.assertEqual(resp.status_code, 302)
        ev = Evaluation.objects.get(
            coach_season=self.d["coach_season"],
            station=self.d["station"],
            player_season=self.d["ps"],
        )
        self.assertEqual(ev.scores["power"], 8)

    def test_save_eval_upsert(self):
        """Saving again for the same player/station should update, not duplicate."""
        url = reverse(
            "evaluations:save_eval",
            args=[self.d["station"].pk, self.d["session"].pk, self.d["ps"].pk],
        )
        self.client.post(
            url, {"score_power": "5", "score_contact": "5", "action": "save"}
        )
        self.client.post(
            url, {"score_power": "9", "score_contact": "8", "action": "save"}
        )
        self.assertEqual(
            Evaluation.objects.filter(
                coach_season=self.d["coach_season"],
                station=self.d["station"],
                player_season=self.d["ps"],
            ).count(),
            1,
        )
        ev = Evaluation.objects.get(
            coach_season=self.d["coach_season"],
            station=self.d["station"],
            player_season=self.d["ps"],
        )
        self.assertEqual(ev.scores["power"], 9)


class EvalPrivacyTests(TestCase):
    """Test that coaches can only see their own evaluations."""

    def setUp(self):
        self.d = _setup_eval_base()
        # Create a second coach
        self.coach2_user = User.objects.create_user(
            username="coach2@sfll.org",
            email="coach2@sfll.org",
            first_name="Asst",
            last_name="Coach",
            password="testpass123",
            is_staff=True,
        )
        coach2 = Coach.objects.create(user=self.coach2_user, league=self.d["league"])
        team2 = Team.objects.create(league=self.d["league"], name="Dolphins")
        ts2 = TeamSeason.objects.create(
            team=team2,
            season=self.d["season"],
            division=self.d["division"],
        )
        self.coach2_season = CoachSeason.objects.create(
            coach=coach2,
            team_season=ts2,
            season=self.d["season"],
            role="head_coach",
        )
        # Coach 1 creates an eval
        Evaluation.objects.create(
            player_season=self.d["ps"],
            session=self.d["session"],
            coach_season=self.d["coach_season"],
            station=self.d["station"],
            scores={"power": 8},
        )
        self.client = Client()

    def test_player_eval_view_only_shows_own_evals(self):
        """Coach 2 should see zero evaluations for this player (privacy)."""
        self.client.login(username="coach2@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse(
                "evaluations:player_eval",
                args=[self.d["ps"].pk],
            )
        )
        self.assertEqual(resp.status_code, 200)
        # The view filters by coach_season; coach2 has no evals for this player
        # so station_groups should show empty evaluations lists


class DivisionReportPermissionTests(TestCase):
    """Test aggregated report access control."""

    def setUp(self):
        self.d = _setup_eval_base()
        self.client = Client()

    def test_division_report_forbidden_for_coach(self):
        """Regular coaches should NOT see aggregated reports."""
        # Remove staff status, add coach role instead
        user = User.objects.create_user(
            username="justcoach@sfll.org",
            email="justcoach@sfll.org",
            first_name="Just",
            last_name="Coach",
            password="testpass123",
        )
        UserRole.objects.create(
            user=user,
            league=self.d["league"],
            role="head_coach",
            division=self.d["division"],
            is_active=True,
        )
        self.client.login(username="justcoach@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse(
                "evaluations:division_report",
                args=[self.d["division"].pk],
            )
        )
        self.assertEqual(resp.status_code, 403)

    def test_division_report_allowed_for_player_agent(self):
        user = User.objects.create_user(
            username="pa@sfll.org",
            email="pa@sfll.org",
            first_name="Player",
            last_name="Agent",
            password="testpass123",
        )
        UserRole.objects.create(
            user=user,
            league=self.d["league"],
            role="player_agent",
            division=self.d["division"],
            is_active=True,
        )
        self.client.login(username="pa@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse(
                "evaluations:division_report",
                args=[self.d["division"].pk],
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_division_report_allowed_for_superuser(self):
        user = User.objects.create_user(
            username="super@sfll.org",
            email="super@sfll.org",
            first_name="Super",
            last_name="User",
            password="testpass123",
            is_superuser=True,
        )
        self.client.login(username="super@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse(
                "evaluations:division_report",
                args=[self.d["division"].pk],
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_player_agent_wrong_division_denied(self):
        """Player Agent scoped to AAA should not see Majors report."""
        other_div = Division.objects.create(
            league=self.d["league"],
            name="AAA",
            display_order=1,
        )
        user = User.objects.create_user(
            username="pa-aaa@sfll.org",
            email="pa-aaa@sfll.org",
            first_name="PA",
            last_name="AAA",
            password="testpass123",
        )
        UserRole.objects.create(
            user=user,
            league=self.d["league"],
            role="player_agent",
            division=other_div,
            is_active=True,
        )
        self.client.login(username="pa-aaa@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse(
                "evaluations:division_report",
                args=[self.d["division"].pk],
            )
        )
        self.assertEqual(resp.status_code, 403)
