"""Tests for the tryouts app — Session, SessionAssignment, CheckIn models and views."""

from datetime import date, time, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Coach, CoachSeason, User, UserRole
from core.models import AuditLog
from evaluations.models import Evaluation
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
from tryouts.models import CheckIn, Session, SessionAssignment, WalkIn


def _setup_base():
    """Create league, season, division, and user. Returns dict of objects."""
    league = League.objects.create(name="SFLL", short_name="SFLL")
    season = Season.objects.create(
        league=league,
        name="Spring 2026",
        year=2026,
        season_type="spring",
        is_active=True,
    )
    division = Division.objects.create(league=league, name="Majors", display_order=0)
    return {"league": league, "season": season, "division": division}


def _create_user(email="user@sfll.org", password="testpass123", is_superuser=False):
    return User.objects.create_user(
        username=email,
        email=email,
        first_name="Test",
        last_name="User",
        password=password,
        is_superuser=is_superuser,
    )


def _create_player(league, sc_id="SC-001", first="Jayden", last="Rodriguez"):
    return Player.objects.create(
        league=league,
        sportsconnect_player_id=sc_id,
        first_name=first,
        last_name=last,
    )


class SessionModelTests(TestCase):
    def setUp(self):
        self.base = _setup_base()

    def test_str(self):
        session = Session.objects.create(
            season=self.base["season"],
            name="SES Day 1",
            date=date(2026, 3, 28),
            start_time=time(9, 0),
            division=self.base["division"],
        )
        self.assertIn("SES Day 1", str(session))
        self.assertIn("2026-03-28", str(session))

    def test_is_makeup_default(self):
        session = Session.objects.create(
            season=self.base["season"],
            name="SES Day 1",
            date=date(2026, 3, 28),
            start_time=time(9, 0),
            division=self.base["division"],
        )
        self.assertFalse(session.is_makeup)
        self.assertIsNone(session.makeup_for)

    def test_makeup_session_link(self):
        original = Session.objects.create(
            season=self.base["season"],
            name="SES 1",
            date=date(2026, 3, 28),
            start_time=time(9, 0),
            division=self.base["division"],
        )
        makeup = Session.objects.create(
            season=self.base["season"],
            name="SES 1 Makeup",
            date=date(2026, 4, 5),
            start_time=time(9, 0),
            division=self.base["division"],
            is_makeup=True,
            makeup_for=original,
        )
        self.assertEqual(makeup.makeup_for, original)
        self.assertIn(makeup, original.makeup_sessions.all())


class SessionAssignmentModelTests(TestCase):
    def setUp(self):
        self.base = _setup_base()
        self.player = _create_player(self.base["league"])
        self.ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.base["season"],
            division=self.base["division"],
        )
        self.session = Session.objects.create(
            season=self.base["season"],
            name="SES 1",
            date=date(2026, 3, 28),
            start_time=time(9, 0),
            division=self.base["division"],
        )

    def test_create_assignment(self):
        sa = SessionAssignment.objects.create(
            session=self.session,
            player_season=self.ps,
        )
        self.assertIn("SES 1", str(sa))

    def test_unique_together(self):
        SessionAssignment.objects.create(
            session=self.session,
            player_season=self.ps,
        )
        with self.assertRaises(Exception):
            SessionAssignment.objects.create(
                session=self.session,
                player_season=self.ps,
            )


class CheckInModelTests(TestCase):
    def setUp(self):
        self.base = _setup_base()
        self.player = _create_player(self.base["league"])
        self.ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.base["season"],
            division=self.base["division"],
        )
        self.session = Session.objects.create(
            season=self.base["season"],
            name="SES 1",
            date=date.today(),
            start_time=time(9, 0),
            division=self.base["division"],
        )
        self.assignment = SessionAssignment.objects.create(
            session=self.session,
            player_season=self.ps,
        )

    def test_create_checkin(self):
        checkin = CheckIn.objects.create(
            session_assignment=self.assignment,
        )
        self.assertIsNotNone(checkin.checked_in_at)
        self.assertIn("Check-in", str(checkin))

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
        resp = self.client.get(reverse("tryouts:session_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_session_list_authenticated(self):
        user = _create_user()
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:session_list"))
        self.assertEqual(resp.status_code, 200)

    def test_session_create_forbidden_for_regular_user(self):
        user = _create_user()
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:session_create"))
        self.assertEqual(resp.status_code, 403)

    def test_session_create_allowed_for_superuser(self):
        user = _create_user(email="admin@sfll.org", is_superuser=True)
        self.client.login(username="admin@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:session_create"))
        self.assertEqual(resp.status_code, 200)

    def test_session_create_allowed_for_cto_role(self):
        user = _create_user(email="cto@sfll.org")
        UserRole.objects.create(
            user=user,
            league=self.base["league"],
            role="cto",
            is_active=True,
        )
        self.client.login(username="cto@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:session_create"))
        self.assertEqual(resp.status_code, 200)

    def test_session_create_allowed_for_player_agent(self):
        user = _create_user(email="pa@sfll.org")
        UserRole.objects.create(
            user=user,
            league=self.base["league"],
            role="player_agent",
            division=self.base["division"],
            is_active=True,
        )
        self.client.login(username="pa@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:session_create"))
        self.assertEqual(resp.status_code, 200)

    def test_session_delete_forbidden_for_regular_user(self):
        user = _create_user()
        session = Session.objects.create(
            season=self.base["season"],
            name="SES 1",
            date=date.today(),
            start_time=time(9, 0),
            division=self.base["division"],
        )
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:session_delete", args=[session.pk]))
        self.assertEqual(resp.status_code, 403)


class CheckInViewTests(TestCase):
    """Test check-in views and the public QR-code check-in flow."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.player = _create_player(self.base["league"])
        self.ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.base["season"],
            division=self.base["division"],
        )
        self.session = Session.objects.create(
            season=self.base["season"],
            name="SES 1",
            date=date.today(),
            start_time=time(9, 0),
            division=self.base["division"],
        )
        self.assignment = SessionAssignment.objects.create(
            session=self.session,
            player_season=self.ps,
            assigned_by=self.user,
        )
        self.client = Client()

    def test_checkin_dashboard_requires_permission(self):
        regular_user = _create_user(email="nobody@sfll.org")
        self.client.login(username="nobody@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("tryouts:session_checkin", args=[self.session.pk])
        )
        self.assertEqual(resp.status_code, 403)

    def test_checkin_dashboard_allowed_for_front_desk(self):
        fd_user = _create_user(email="fd@sfll.org")
        UserRole.objects.create(
            user=fd_user,
            league=self.base["league"],
            role="front_desk",
            is_active=True,
        )
        self.client.login(username="fd@sfll.org", password="testpass123")
        resp = self.client.get(
            reverse("tryouts:session_checkin", args=[self.session.pk])
        )
        self.assertEqual(resp.status_code, 200)

    def test_checkin_player_via_post(self):
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.post(
            reverse(
                "tryouts:checkin_player", args=[self.session.pk, self.assignment.pk]
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            CheckIn.objects.filter(session_assignment=self.assignment).exists()
        )

    def test_checkin_player_idempotent(self):
        """Checking in the same player twice should not create duplicate."""
        self.client.login(username="user@sfll.org", password="testpass123")
        self.client.post(
            reverse(
                "tryouts:checkin_player", args=[self.session.pk, self.assignment.pk]
            )
        )
        self.client.post(
            reverse(
                "tryouts:checkin_player", args=[self.session.pk, self.assignment.pk]
            )
        )
        self.assertEqual(
            CheckIn.objects.filter(session_assignment=self.assignment).count(), 1
        )

    def test_public_checkin_by_token_get_shows_confirm(self):
        """GET should show confirmation page without creating a CheckIn."""
        resp = self.client.get(reverse("public_checkin", args=[self.ps.checkin_token]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            CheckIn.objects.filter(session_assignment=self.assignment).exists()
        )
        self.assertTrue(resp.context["confirm_checkin"])

    def test_public_checkin_by_token_post_creates_checkin(self):
        """POST should create a CheckIn and show the success state."""
        resp = self.client.post(reverse("public_checkin", args=[self.ps.checkin_token]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            CheckIn.objects.filter(session_assignment=self.assignment).exists()
        )

    def test_public_checkin_already_checked_in(self):
        """If already checked in, both GET and POST should show already_checked_in."""
        CheckIn.objects.create(session_assignment=self.assignment)
        resp = self.client.get(reverse("public_checkin", args=[self.ps.checkin_token]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["already_checked_in"])

    def test_public_checkin_no_session_today(self):
        """If no session today, public check-in shows an error."""
        self.session.date = date.today() - timedelta(days=1)
        self.session.save()
        resp = self.client.get(reverse("public_checkin", args=[self.ps.checkin_token]))
        self.assertEqual(resp.status_code, 200)


class SessionCreatePostTests(TestCase):
    """Test session creation via POST."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.client = Client()
        self.client.login(username="user@sfll.org", password="testpass123")

    def test_create_session_post(self):
        resp = self.client.post(
            reverse("tryouts:session_create"),
            {
                "name": "SES Day 1",
                "date": "2026-03-28",
                "start_time": "09:00",
                "division": self.base["division"].pk,
                "location": "Field 3",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Session.objects.filter(name="SES Day 1").exists())

    def test_create_session_missing_required(self):
        resp = self.client.post(
            reverse("tryouts:session_create"),
            {
                "name": "",
                "date": "",
                "start_time": "",
                "division": "",
            },
        )
        # Should re-render form (200), not redirect
        self.assertEqual(resp.status_code, 200)

    def test_create_session_invalid_date_format(self):
        """Malformed date must re-render with error, not 500."""
        resp = self.client.post(
            reverse("tryouts:session_create"),
            {
                "name": "Bad Date",
                "date": "2026-13-40",
                "start_time": "09:00",
                "division": self.base["division"].pk,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Session.objects.filter(name="Bad Date").exists())

    def test_create_session_invalid_start_time_format(self):
        """'9am' or bare digits must re-render with error, not 500."""
        for bad_time in ("9am", "0900", "09:00+00:00"):
            resp = self.client.post(
                reverse("tryouts:session_create"),
                {
                    "name": "Bad Time",
                    "date": "2026-03-28",
                    "start_time": bad_time,
                    "division": self.base["division"].pk,
                },
            )
            self.assertEqual(
                resp.status_code,
                200,
                msg=f"Expected 200 for start_time={bad_time!r}",
            )
            self.assertFalse(Session.objects.filter(name="Bad Time").exists())

    def test_create_session_invalid_end_time_format(self):
        """Invalid end_time must re-render with error, not 500."""
        resp = self.client.post(
            reverse("tryouts:session_create"),
            {
                "name": "Bad End",
                "date": "2026-03-28",
                "start_time": "09:00",
                "end_time": "bad",
                "division": self.base["division"].pk,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Session.objects.filter(name="Bad End").exists())

    def test_create_session_action_label_on_create(self):
        """Success message must say 'created', not 'updated'."""
        resp = self.client.post(
            reverse("tryouts:session_create"),
            {
                "name": "Action Test",
                "date": "2026-03-28",
                "start_time": "09:00",
                "division": self.base["division"].pk,
            },
            follow=True,
        )
        messages = [str(m) for m in resp.context["messages"]]
        self.assertTrue(
            any("created" in m for m in messages),
            msg=f"Expected 'created' in messages, got: {messages}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# SES Session screen (SFLL-96 / Phase 5)
# ─────────────────────────────────────────────────────────────────────────────


def _setup_ses_session(*, num_registered=6, num_checked_in=4, num_on_station=2):
    """Build a session with predictable registered/checked-in/on-station counts.

    Returns dict with: league, season, division, station1, station2, session,
    players (list), assignments (list), and a helper-created CoachSeason.
    """
    base = _setup_base()
    league = base["league"]
    season = base["season"]
    division = base["division"]

    station1 = Station.objects.create(league=league, name="Hitting", display_order=0)
    station2 = Station.objects.create(league=league, name="Infield", display_order=1)

    session = Session.objects.create(
        season=season,
        name="SES Day 1",
        date=date.today(),
        start_time=time(9, 0),
        division=division,
    )

    # Coach for evaluations
    coach_user = User.objects.create_user(
        username="coach@sfll.org",
        email="coach@sfll.org",
        password="testpass123",
        first_name="Pat",
        last_name="Coach",
    )
    coach = Coach.objects.create(user=coach_user, league=league)
    team = Team.objects.create(league=league, name="Giants")
    team_season = TeamSeason.objects.create(
        team=team,
        season=season,
        division=division,
    )
    coach_season = CoachSeason.objects.create(
        coach=coach,
        team_season=team_season,
        season=season,
        role="head_coach",
    )

    players = []
    assignments = []
    for i in range(num_registered):
        p = Player.objects.create(
            league=league,
            sportsconnect_player_id=f"SC-{i:03d}",
            first_name=f"P{i}",
            last_name=f"Last{i}",
        )
        ps = PlayerSeason.objects.create(
            player=p,
            season=season,
            division=division,
        )
        sa = SessionAssignment.objects.create(session=session, player_season=ps)
        players.append((p, ps))
        assignments.append(sa)

    # First N register check-ins
    for sa in assignments[:num_checked_in]:
        CheckIn.objects.create(session_assignment=sa)

    # First M of the checked-in players get at least one evaluation
    for sa in assignments[:num_on_station]:
        Evaluation.objects.create(
            player_season=sa.player_season,
            session=session,
            coach_season=coach_season,
            station=station1,
            scores={"power": 4},
        )

    return {
        "league": league,
        "season": season,
        "division": division,
        "station1": station1,
        "station2": station2,
        "session": session,
        "players": players,
        "assignments": assignments,
        "coach_season": coach_season,
    }


class SesSessionScreenTests(TestCase):
    """Stat row + per-station progress on the SES Session screen."""

    def setUp(self):
        self.fixture = _setup_ses_session(
            num_registered=6,
            num_checked_in=4,
            num_on_station=2,
        )
        self.user = _create_user(is_superuser=True)
        self.client = Client()
        self.client.login(username="user@sfll.org", password="testpass123")

    def test_stat_row_counts(self):
        resp = self.client.get(
            reverse("tryouts:session_detail", args=[self.fixture["session"].pk])
        )
        self.assertEqual(resp.status_code, 200)
        stats = resp.context["stats"]
        self.assertEqual(stats["registered"], 6)
        self.assertEqual(stats["checked_in"], 4)
        self.assertEqual(stats["no_show"], 2)
        self.assertEqual(stats["on_station"], 2)

    def test_no_show_excludes_checked_in_players(self):
        resp = self.client.get(
            reverse("tryouts:session_detail", args=[self.fixture["session"].pk])
        )
        no_show_pks = {item["assignment"].pk for item in resp.context["no_show_queue"]}
        checked_in_pks = {
            sa.pk
            for sa in self.fixture["assignments"]
            if CheckIn.objects.filter(session_assignment=sa).exists()
        }
        self.assertEqual(len(no_show_pks & checked_in_pks), 0)
        self.assertEqual(len(no_show_pks), 2)

    def test_station_progress_pct_and_state(self):
        resp = self.client.get(
            reverse("tryouts:session_detail", args=[self.fixture["session"].pk])
        )
        progress = {p["station"].pk: p for p in resp.context["station_progress"]}
        s1 = progress[self.fixture["station1"].pk]
        s2 = progress[self.fixture["station2"].pk]
        # Hitting: 2 of 4 checked-in evaluated → 50%, in_progress.
        self.assertEqual(s1["evaluated"], 2)
        self.assertEqual(s1["expected"], 4)
        self.assertEqual(s1["pct"], 50)
        self.assertEqual(s1["state"], "in_progress")
        # Infield: 0 of 4 → idle.
        self.assertEqual(s2["evaluated"], 0)
        self.assertEqual(s2["state"], "idle")

    def test_station_progress_handles_zero_checked_in(self):
        # Brand new session — no check-ins yet.
        empty_session = Session.objects.create(
            season=self.fixture["season"],
            name="SES Day 2",
            date=date.today() + timedelta(days=7),
            start_time=time(9, 0),
            division=self.fixture["division"],
        )
        resp = self.client.get(
            reverse("tryouts:session_detail", args=[empty_session.pk])
        )
        for p in resp.context["station_progress"]:
            self.assertEqual(p["expected"], 0)
            self.assertEqual(p["pct"], 0)
            self.assertEqual(p["state"], "idle")


class SesRosterSearchTests(TestCase):
    """HTMX search endpoint on the SES Session screen check-in roster."""

    def setUp(self):
        self.fixture = _setup_ses_session()
        self.user = _create_user(is_superuser=True)
        self.client = Client()
        self.client.login(username="user@sfll.org", password="testpass123")

    def test_search_filters_by_last_name(self):
        url = reverse("tryouts:ses_roster_search", args=[self.fixture["session"].pk])
        resp = self.client.get(url, {"q": "Last3"})
        self.assertEqual(resp.status_code, 200)
        roster_pks = [r["assignment"].pk for r in resp.context["roster"]]
        # P3 / Last3 only.
        self.assertEqual(len(roster_pks), 1)

    def test_empty_search_returns_full_roster(self):
        url = reverse("tryouts:ses_roster_search", args=[self.fixture["session"].pk])
        resp = self.client.get(url, {"q": ""})
        self.assertEqual(len(resp.context["roster"]), 6)

    def test_no_match_shows_empty_state(self):
        url = reverse("tryouts:ses_roster_search", args=[self.fixture["session"].pk])
        resp = self.client.get(url, {"q": "ZZZZ"})
        self.assertEqual(len(resp.context["roster"]), 0)
        self.assertContains(resp, "No players match")


class SesQuickCheckinTests(TestCase):
    """HTMX one-click check-in from the SES Session screen."""

    def setUp(self):
        self.fixture = _setup_ses_session(
            num_registered=3,
            num_checked_in=0,
            num_on_station=0,
        )
        self.user = _create_user(is_superuser=True)
        self.client = Client()
        self.client.login(username="user@sfll.org", password="testpass123")

    def test_quick_checkin_creates_record(self):
        sa = self.fixture["assignments"][0]
        url = reverse(
            "tryouts:ses_quick_checkin",
            args=[self.fixture["session"].pk, sa.pk],
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(CheckIn.objects.filter(session_assignment=sa).exists())

    def test_quick_checkin_returns_row_with_oob_swaps(self):
        sa = self.fixture["assignments"][0]
        url = reverse(
            "tryouts:ses_quick_checkin",
            args=[self.fixture["session"].pk, sa.pk],
        )
        resp = self.client.post(url)
        # Primary swap target — the row id.
        self.assertContains(resp, f'id="ses-row-{sa.pk}"')
        # OOB swap for stat row + no-show queue.
        self.assertContains(resp, 'id="ses-stats"')
        self.assertContains(resp, 'hx-swap-oob="innerHTML"')
        self.assertContains(resp, 'id="ses-noshow"')

    def test_quick_checkin_idempotent(self):
        sa = self.fixture["assignments"][0]
        url = reverse(
            "tryouts:ses_quick_checkin",
            args=[self.fixture["session"].pk, sa.pk],
        )
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(
            CheckIn.objects.filter(session_assignment=sa).count(),
            1,
        )

    def test_quick_checkin_requires_permission(self):
        # Regular user without check-in roles.
        self.client.logout()
        _create_user(email="nobody@sfll.org")
        self.client.login(username="nobody@sfll.org", password="testpass123")
        sa = self.fixture["assignments"][0]
        url = reverse(
            "tryouts:ses_quick_checkin",
            args=[self.fixture["session"].pk, sa.pk],
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)


class SesQuickRescheduleTests(TestCase):
    """One-click reschedule of a no-show to the next available session."""

    def setUp(self):
        self.fixture = _setup_ses_session(
            num_registered=2,
            num_checked_in=0,
            num_on_station=0,
        )
        self.user = _create_user(is_superuser=True)
        self.client = Client()
        self.client.login(username="user@sfll.org", password="testpass123")
        self.session = self.fixture["session"]
        # An upcoming makeup session in the same division.
        self.makeup = Session.objects.create(
            season=self.fixture["season"],
            name="SES Makeup",
            date=date.today() + timedelta(days=7),
            start_time=time(9, 0),
            division=self.fixture["division"],
            is_makeup=True,
            makeup_for=self.session,
        )

    def test_reschedule_picks_makeup_target(self):
        sa = self.fixture["assignments"][0]
        url = reverse(
            "tryouts:ses_quick_reschedule",
            args=[self.session.pk, sa.pk],
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        # Original assignment removed, new one in makeup session.
        self.assertFalse(SessionAssignment.objects.filter(pk=sa.pk).exists())
        self.assertTrue(
            SessionAssignment.objects.filter(
                session=self.makeup,
                player_season=sa.player_season,
            ).exists()
        )

    def test_reschedule_flags_player_needs_makeup(self):
        sa = self.fixture["assignments"][0]
        ps = sa.player_season
        url = reverse(
            "tryouts:ses_quick_reschedule",
            args=[self.session.pk, sa.pk],
        )
        self.client.post(url)
        ps.refresh_from_db()
        self.assertEqual(ps.status, "needs_makeup")

    def test_reschedule_records_audit_log(self):
        sa = self.fixture["assignments"][0]
        url = reverse(
            "tryouts:ses_quick_reschedule",
            args=[self.session.pk, sa.pk],
        )
        self.client.post(url)
        log = AuditLog.objects.filter(action="player.quick_reschedule").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.details["to_session_id"], self.makeup.pk)

    def test_reschedule_falls_back_to_regular_session(self):
        # No makeup — fall back to the next regular session.
        self.makeup.delete()
        regular = Session.objects.create(
            season=self.fixture["season"],
            name="SES Day 2",
            date=date.today() + timedelta(days=14),
            start_time=time(9, 0),
            division=self.fixture["division"],
        )
        sa = self.fixture["assignments"][0]
        url = reverse(
            "tryouts:ses_quick_reschedule",
            args=[self.session.pk, sa.pk],
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            SessionAssignment.objects.filter(
                session=regular,
                player_season=sa.player_season,
            ).exists()
        )

    def test_reschedule_returns_200_with_inline_message_when_no_target(self):
        # Remove all other sessions in the division so there is no target.
        self.makeup.delete()
        sa = self.fixture["assignments"][0]
        url = reverse(
            "tryouts:ses_quick_reschedule",
            args=[self.session.pk, sa.pk],
        )
        resp = self.client.post(url)
        # 200 so HTMX can swap the inline error message into the target element.
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"No upcoming session", resp.content)
        # Original assignment untouched.
        self.assertTrue(SessionAssignment.objects.filter(pk=sa.pk).exists())

    def test_reschedule_requires_permission(self):
        self.client.logout()
        _create_user(email="nobody@sfll.org")
        self.client.login(username="nobody@sfll.org", password="testpass123")
        sa = self.fixture["assignments"][0]
        url = reverse(
            "tryouts:ses_quick_reschedule",
            args=[self.session.pk, sa.pk],
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_reschedule_handles_player_already_in_target(self):
        # Defensive: shouldn't 500 if the player already has an assignment.
        sa = self.fixture["assignments"][0]
        SessionAssignment.objects.create(
            session=self.makeup,
            player_season=sa.player_season,
        )
        url = reverse(
            "tryouts:ses_quick_reschedule",
            args=[self.session.pk, sa.pk],
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        # Original assignment still removed.
        self.assertFalse(SessionAssignment.objects.filter(pk=sa.pk).exists())


class KioskViewTests(TestCase):
    """SFLL-115 — front-desk iPad kiosk."""

    def setUp(self):
        self.base = _setup_base()
        self.user = _create_user(is_superuser=True)
        self.player = _create_player(self.base["league"])
        self.ps = PlayerSeason.objects.create(
            player=self.player,
            season=self.base["season"],
            division=self.base["division"],
        )
        self.session = Session.objects.create(
            season=self.base["season"],
            name="SES Today",
            date=date.today(),
            start_time=time(9, 0),
            division=self.base["division"],
        )
        self.assignment = SessionAssignment.objects.create(
            session=self.session,
            player_season=self.ps,
            assigned_by=self.user,
        )
        self.client = Client()

    def test_kiosk_requires_login(self):
        resp = self.client.get(reverse("tryouts:kiosk"))
        self.assertEqual(resp.status_code, 302)

    def test_kiosk_requires_checkin_permission(self):
        _create_user(email="nobody@sfll.org")
        self.client.login(username="nobody@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:kiosk"))
        self.assertEqual(resp.status_code, 403)

    def test_kiosk_renders_for_superuser(self):
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:kiosk"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "kiosk-grid")
        self.assertContains(resp, self.player.last_name)
        self.assertContains(resp, "Tap to check in")

    def test_kiosk_renders_for_front_desk(self):
        fd = _create_user(email="fd@sfll.org")
        UserRole.objects.create(
            user=fd,
            league=self.base["league"],
            role="front_desk",
            is_active=True,
        )
        self.client.login(username="fd@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:kiosk"))
        self.assertEqual(resp.status_code, 200)

    def test_kiosk_excludes_other_days(self):
        future_session = Session.objects.create(
            season=self.base["season"],
            name="SES Tomorrow",
            date=date.today() + timedelta(days=1),
            start_time=time(9, 0),
            division=self.base["division"],
        )
        other_player = _create_player(
            self.base["league"], sc_id="SC-002", first="Mira", last="Khan"
        )
        other_ps = PlayerSeason.objects.create(
            player=other_player,
            season=self.base["season"],
            division=self.base["division"],
        )
        SessionAssignment.objects.create(
            session=future_session,
            player_season=other_ps,
            assigned_by=self.user,
        )
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:kiosk"))
        self.assertContains(resp, "Rodriguez")
        self.assertNotContains(resp, "Khan")

    def test_kiosk_search_partial_filters_by_name(self):
        other_player = _create_player(
            self.base["league"], sc_id="SC-002", first="Mira", last="Khan"
        )
        other_ps = PlayerSeason.objects.create(
            player=other_player,
            season=self.base["season"],
            division=self.base["division"],
        )
        SessionAssignment.objects.create(
            session=self.session,
            player_season=other_ps,
            assigned_by=self.user,
        )
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:kiosk_search"), {"q": "mira"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Khan")
        self.assertNotContains(resp, "Rodriguez")

    def test_kiosk_checkin_creates_record(self):
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.post(
            reverse("tryouts:kiosk_checkin", args=[self.assignment.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            CheckIn.objects.filter(session_assignment=self.assignment).exists()
        )
        self.assertContains(resp, "kiosk-feed")
        self.assertContains(resp, "kiosk-checked-in-count")

    def test_kiosk_checkin_idempotent(self):
        self.client.login(username="user@sfll.org", password="testpass123")
        self.client.post(reverse("tryouts:kiosk_checkin", args=[self.assignment.pk]))
        self.client.post(reverse("tryouts:kiosk_checkin", args=[self.assignment.pk]))
        self.assertEqual(
            CheckIn.objects.filter(session_assignment=self.assignment).count(), 1
        )

    def test_kiosk_checkin_rejects_non_today_assignment(self):
        yesterday_session = Session.objects.create(
            season=self.base["season"],
            name="SES Yesterday",
            date=date.today() - timedelta(days=1),
            start_time=time(9, 0),
            division=self.base["division"],
        )
        other_player = _create_player(
            self.base["league"], sc_id="SC-004", first="Old", last="Day"
        )
        other_ps = PlayerSeason.objects.create(
            player=other_player,
            season=self.base["season"],
            division=self.base["division"],
        )
        past_assignment = SessionAssignment.objects.create(
            session=yesterday_session,
            player_season=other_ps,
            assigned_by=self.user,
        )
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.post(
            reverse("tryouts:kiosk_checkin", args=[past_assignment.pk])
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(
            CheckIn.objects.filter(session_assignment=past_assignment).exists()
        )

    def test_kiosk_session_filter_narrows_grid(self):
        other_session = Session.objects.create(
            season=self.base["season"],
            name="SES Afternoon",
            date=date.today(),
            start_time=time(13, 0),
            division=self.base["division"],
        )
        other_player = _create_player(
            self.base["league"], sc_id="SC-003", first="Sam", last="Park"
        )
        other_ps = PlayerSeason.objects.create(
            player=other_player,
            season=self.base["season"],
            division=self.base["division"],
        )
        SessionAssignment.objects.create(
            session=other_session,
            player_season=other_ps,
            assigned_by=self.user,
        )
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.get(reverse("tryouts:kiosk"), {"session": self.session.pk})
        self.assertContains(resp, "Rodriguez")
        self.assertNotContains(resp, "Park")

    def test_kiosk_walkin_creates_record(self):
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.post(
            reverse("tryouts:kiosk_walkin"),
            {
                "first_name": "Marco",
                "last_name": "Reyes",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            WalkIn.objects.filter(first_name="Marco", last_name="Reyes").exists()
        )
        self.assertContains(resp, "kiosk-feed")
        self.assertContains(resp, "kiosk-walkin-list")

    def test_kiosk_walkin_requires_name(self):
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.post(
            reverse("tryouts:kiosk_walkin"), {"first_name": "", "last_name": ""}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(WalkIn.objects.exists())

    def test_kiosk_walkin_requires_login(self):
        resp = self.client.post(
            reverse("tryouts:kiosk_walkin"),
            {
                "first_name": "Marco",
                "last_name": "Reyes",
            },
        )
        self.assertEqual(resp.status_code, 302)

    def test_kiosk_walkin_requires_checkin_permission(self):
        _create_user(email="noperm@sfll.org")
        self.client.login(username="noperm@sfll.org", password="testpass123")
        resp = self.client.post(
            reverse("tryouts:kiosk_walkin"),
            {
                "first_name": "Marco",
                "last_name": "Reyes",
            },
        )
        self.assertEqual(resp.status_code, 403)

    def test_kiosk_walkin_with_session(self):
        self.client.login(username="user@sfll.org", password="testpass123")
        self.client.post(
            reverse("tryouts:kiosk_walkin"),
            {
                "first_name": "Ana",
                "last_name": "Silva",
                "session": self.session.pk,
            },
        )
        wi = WalkIn.objects.get(first_name="Ana", last_name="Silva")
        self.assertEqual(wi.session, self.session)
        self.assertEqual(wi.division, self.session.division)

    def test_kiosk_walkin_without_session_still_visible(self):
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.post(
            reverse("tryouts:kiosk_walkin"),
            {
                "first_name": "Joe",
                "last_name": "NoSession",
            },
        )
        self.assertEqual(resp.status_code, 200)
        wi = WalkIn.objects.get(first_name="Joe", last_name="NoSession")
        self.assertIsNone(wi.session)
        self.assertEqual(wi.season, self.base["season"])
        self.assertContains(resp, "NoSession")

    def test_kiosk_checkin_includes_walkin_list(self):
        self.client.login(username="user@sfll.org", password="testpass123")
        resp = self.client.post(
            reverse("tryouts:kiosk_checkin", args=[self.assignment.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "kiosk-walkin-list")
