"""Tests for the communications app — EmailTemplate, EmailLog, RSVP models and views."""

from datetime import date, time

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User, UserRole
from communications.models import RSVP, EmailLog, EmailTemplate
from players.models import Division, League, Player, PlayerSeason, Season
from tryouts.models import Session, SessionAssignment


def _setup_comms_base():
    """Create base objects for communications tests."""
    league = League.objects.create(name="SFLL", short_name="SFLL")
    season = Season.objects.create(
        league=league,
        name="Spring 2026",
        year=2026,
        season_type="spring",
        is_active=True,
    )
    division = Division.objects.create(league=league, name="Majors", display_order=0)
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
        account_name="Maria Rodriguez",
        account_email="maria@example.com",
    )
    session = Session.objects.create(
        season=season,
        name="SES 1",
        date=date(2026, 3, 28),
        start_time=time(9, 0),
        division=division,
        location="Field 3",
    )
    assignment = SessionAssignment.objects.create(
        session=session,
        player_season=ps,
    )
    template = EmailTemplate.objects.create(
        league=league,
        name="SES Invitation",
        subject_template="{{ player.first_name }} — Your SES Session",
        body_template="Dear {{ player.first_name }},\n\nYou are scheduled for {{ session.name }}.",
        is_active=True,
    )
    return {
        "league": league,
        "season": season,
        "division": division,
        "player": player,
        "ps": ps,
        "session": session,
        "assignment": assignment,
        "template": template,
    }


def _create_comms_user(email="comms@sfll.org", password="testpass123"):
    return User.objects.create_user(
        username=email,
        email=email,
        first_name="Comms",
        last_name="Editor",
        password=password,
    )


class EmailTemplateModelTests(TestCase):
    def setUp(self):
        self.d = _setup_comms_base()

    def test_str(self):
        self.assertEqual(str(self.d["template"]), "SES Invitation")

    def test_default_active(self):
        t = EmailTemplate.objects.create(
            league=self.d["league"],
            name="Test",
            subject_template="s",
            body_template="b",
        )
        self.assertTrue(t.is_active)


class EmailLogModelTests(TestCase):
    def setUp(self):
        self.d = _setup_comms_base()

    def test_create(self):
        log = EmailLog.objects.create(
            player_season=self.d["ps"],
            template=self.d["template"],
            to_address="maria@example.com",
            subject="Test Subject",
            body_snapshot="Test body",
        )
        self.assertFalse(log.bounced)
        self.assertIn("maria@example.com", str(log))

    def test_ordering_by_sent_at(self):
        EmailLog.objects.create(
            player_season=self.d["ps"],
            to_address="a@b.com",
            subject="First",
            body_snapshot="body",
        )
        EmailLog.objects.create(
            player_season=self.d["ps"],
            to_address="a@b.com",
            subject="Second",
            body_snapshot="body",
        )
        logs = list(EmailLog.objects.all())
        # Most recent first
        self.assertEqual(logs[0].subject, "Second")


class RSVPModelTests(TestCase):
    def setUp(self):
        self.d = _setup_comms_base()

    def test_create(self):
        rsvp = RSVP.objects.create(
            player_season=self.d["ps"],
            session=self.d["session"],
            status="attending",
        )
        self.assertEqual(rsvp.response_method, "web")
        self.assertIn("Attending", str(rsvp))

    def test_status_choices(self):
        for status in ("attending", "not_attending", "maybe"):
            rsvp = RSVP.objects.create(
                player_season=self.d["ps"],
                session=self.d["session"],
                status=status,
            )
            rsvp.delete()  # clean up for next iteration


class CommsViewPermissionTests(TestCase):
    """Test that comms views enforce CTO/comms_editor role."""

    def setUp(self):
        self.d = _setup_comms_base()
        self.client = Client()

    def test_comms_home_requires_login(self):
        resp = self.client.get(reverse("communications:index"))
        self.assertEqual(resp.status_code, 302)

    def test_comms_home_forbidden_for_regular_user(self):
        _create_comms_user(email="nobody@sfll.org")
        self.client.login(username="nobody@sfll.org", password="testpass123")
        resp = self.client.get(reverse("communications:index"))
        self.assertEqual(resp.status_code, 403)

    def test_comms_home_allowed_for_comms_editor(self):
        user = _create_comms_user()
        UserRole.objects.create(
            user=user,
            league=self.d["league"],
            role="comms_editor",
            is_active=True,
        )
        self.client.login(username="comms@sfll.org", password="testpass123")
        resp = self.client.get(reverse("communications:index"))
        self.assertEqual(resp.status_code, 200)

    def test_comms_home_allowed_for_superuser(self):
        User.objects.create_user(
            username="super@sfll.org",
            email="super@sfll.org",
            first_name="S",
            last_name="U",
            password="testpass123",
            is_superuser=True,
        )
        self.client.login(username="super@sfll.org", password="testpass123")
        resp = self.client.get(reverse("communications:index"))
        self.assertEqual(resp.status_code, 200)

    def test_template_list_requires_comms_role(self):
        _create_comms_user(email="nobody2@sfll.org")
        self.client.login(username="nobody2@sfll.org", password="testpass123")
        resp = self.client.get(reverse("communications:template_list"))
        self.assertEqual(resp.status_code, 403)


class TemplateViewTests(TestCase):
    def setUp(self):
        self.d = _setup_comms_base()
        self.user = User.objects.create_user(
            username="cto@sfll.org",
            email="cto@sfll.org",
            first_name="CTO",
            last_name="Admin",
            password="testpass123",
            is_superuser=True,
        )
        self.client = Client()
        self.client.login(username="cto@sfll.org", password="testpass123")

    def test_template_list(self):
        resp = self.client.get(reverse("communications:template_list"))
        self.assertEqual(resp.status_code, 200)

    def test_template_create(self):
        resp = self.client.post(
            reverse("communications:template_create"),
            {
                "name": "New Template",
                "subject_template": "{{ player.first_name }} — Info",
                "body_template": "Hello {{ player.first_name }}.",
                "is_active": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(EmailTemplate.objects.filter(name="New Template").exists())

    def test_template_edit(self):
        resp = self.client.post(
            reverse("communications:template_edit", args=[self.d["template"].pk]),
            {
                "name": "Updated Name",
                "subject_template": "Updated Subject",
                "body_template": "Updated body",
                "is_active": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.d["template"].refresh_from_db()
        self.assertEqual(self.d["template"].name, "Updated Name")

    def test_template_preview(self):
        resp = self.client.get(
            reverse("communications:template_preview", args=[self.d["template"].pk])
        )
        self.assertEqual(resp.status_code, 200)


class PublicRSVPTests(TestCase):
    """Test the public RSVP flow (no auth required)."""

    def setUp(self):
        self.d = _setup_comms_base()
        self.client = Client()

    def test_rsvp_page_renders(self):
        resp = self.client.get(reverse("public_rsvp", args=[self.d["ps"].rsvp_token]))
        self.assertEqual(resp.status_code, 200)

    def test_rsvp_submit_attending(self):
        resp = self.client.post(
            reverse("public_rsvp", args=[self.d["ps"].rsvp_token]),
            {"status": "attending"},
        )
        self.assertEqual(resp.status_code, 200)
        rsvp = RSVP.objects.get(
            player_season=self.d["ps"],
            session=self.d["session"],
        )
        self.assertEqual(rsvp.status, "attending")

    def test_rsvp_submit_not_attending(self):
        self.client.post(
            reverse("public_rsvp", args=[self.d["ps"].rsvp_token]),
            {"status": "not_attending"},
        )
        rsvp = RSVP.objects.get(
            player_season=self.d["ps"],
            session=self.d["session"],
        )
        self.assertEqual(rsvp.status, "not_attending")

    def test_rsvp_update_changes_status(self):
        """Submitting again should update, not create a second RSVP."""
        self.client.post(
            reverse("public_rsvp", args=[self.d["ps"].rsvp_token]),
            {"status": "attending"},
        )
        self.client.post(
            reverse("public_rsvp", args=[self.d["ps"].rsvp_token]),
            {"status": "maybe"},
        )
        self.assertEqual(
            RSVP.objects.filter(
                player_season=self.d["ps"],
                session=self.d["session"],
            ).count(),
            1,
        )
        rsvp = RSVP.objects.get(
            player_season=self.d["ps"],
            session=self.d["session"],
        )
        self.assertEqual(rsvp.status, "maybe")

    def test_rsvp_invalid_status(self):
        resp = self.client.post(
            reverse("public_rsvp", args=[self.d["ps"].rsvp_token]),
            {"status": "invalid"},
        )
        self.assertEqual(resp.status_code, 302)  # redirect back
        self.assertFalse(RSVP.objects.filter(player_season=self.d["ps"]).exists())

    def test_rsvp_no_session_assignment(self):
        """Player with no session assignment should see error."""
        player2 = Player.objects.create(
            league=self.d["league"],
            sportsconnect_player_id="SC-999",
            first_name="No",
            last_name="Session",
        )
        ps2 = PlayerSeason.objects.create(
            player=player2,
            season=self.d["season"],
            division=self.d["division"],
        )
        resp = self.client.get(reverse("public_rsvp", args=[ps2.rsvp_token]))
        self.assertEqual(resp.status_code, 200)


class RSVPDashboardTests(TestCase):
    def setUp(self):
        self.d = _setup_comms_base()
        self.user = User.objects.create_user(
            username="cto@sfll.org",
            email="cto@sfll.org",
            first_name="CTO",
            last_name="Admin",
            password="testpass123",
            is_superuser=True,
        )
        self.client = Client()
        self.client.login(username="cto@sfll.org", password="testpass123")

    def test_rsvp_dashboard_renders(self):
        resp = self.client.get(reverse("communications:rsvp_dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_email_log_renders(self):
        resp = self.client.get(reverse("communications:email_log"))
        self.assertEqual(resp.status_code, 200)
