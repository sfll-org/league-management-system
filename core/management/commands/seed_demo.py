"""
Management command to seed demo data for the SFLL — League Management System.

Usage:
    python manage.py seed_demo          # Create demo data
    python manage.py seed_demo --flush  # Delete all data and re-seed
"""

import random
from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Coach, CoachSeason, User
from communications.models import EmailTemplate
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
from tryouts.models import Session, SessionAssignment

FIRST_NAMES = [
    "Jayden",
    "Aiden",
    "Liam",
    "Noah",
    "Ethan",
    "Mason",
    "Lucas",
    "Oliver",
    "Elijah",
    "Logan",
    "Sophia",
    "Isabella",
    "Mia",
    "Charlotte",
    "Amelia",
    "Harper",
    "Evelyn",
    "Abigail",
    "Emily",
    "Luna",
]

LAST_NAMES = [
    "Rodriguez",
    "Martinez",
    "Garcia",
    "Lopez",
    "Hernandez",
    "Gonzalez",
    "Perez",
    "Sanchez",
    "Ramirez",
    "Torres",
    "Rivera",
    "Gomez",
    "Diaz",
    "Reyes",
    "Morales",
    "Cruz",
    "Ortiz",
    "Gutierrez",
    "Chavez",
    "Ramos",
]

TEAM_NAMES = [
    "Marlins",
    "Panthers",
    "Dolphins",
    "Hurricanes",
    "Gators",
    "Rays",
    "Thunder",
    "Lightning",
    "Heat",
    "Sharks",
    "Eagles",
    "Tigers",
]

HITTING_FIELDS = [
    {
        "key": "swing_mechanics",
        "label": "Swing Mechanics",
        "type": "rating",
        "min": 1,
        "max": 5,
    },
    {"key": "contact", "label": "Contact", "type": "rating", "min": 1, "max": 5},
    {"key": "power", "label": "Power", "type": "rating", "min": 1, "max": 5},
]

INFIELD_FIELDS = [
    {"key": "fielding", "label": "Fielding", "type": "rating", "min": 1, "max": 5},
    {"key": "throwing", "label": "Throwing", "type": "rating", "min": 1, "max": 5},
    {"key": "footwork", "label": "Footwork", "type": "rating", "min": 1, "max": 5},
]

OUTFIELD_FIELDS = [
    {"key": "tracking", "label": "Ball Tracking", "type": "rating", "min": 1, "max": 5},
    {
        "key": "arm_strength",
        "label": "Arm Strength",
        "type": "rating",
        "min": 1,
        "max": 5,
    },
    {"key": "speed", "label": "Speed", "type": "rating", "min": 1, "max": 5},
]

PITCHING_FIELDS = [
    {
        "key": "mechanics",
        "label": "Pitching Mechanics",
        "type": "rating",
        "min": 1,
        "max": 5,
    },
    {"key": "accuracy", "label": "Accuracy", "type": "rating", "min": 1, "max": 5},
    {"key": "velocity", "label": "Velocity", "type": "rating", "min": 1, "max": 5},
]


class Command(BaseCommand):
    help = "Seed the database with demo data for SFLL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing data before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing existing data...")
            self._flush()

        self.stdout.write("Seeding demo data...")

        # 1. Superuser
        admin, created = User.objects.get_or_create(
            email="admin@sfll.org",
            defaults={
                "username": "admin@sfll.org",
                "first_name": "Admin",
                "last_name": "SFLL",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password("admin123")
            admin.save()
            self.stdout.write(
                self.style.SUCCESS("  Created superuser: admin@sfll.org / admin123")
            )
        else:
            self.stdout.write("  Superuser already exists.")

        # 2. League
        league, _ = League.objects.get_or_create(
            short_name="SFLL",
            defaults={
                "name": "San Francisco Little League",
                "domain": "sfll.org",
                "timezone": "America/New_York",
            },
        )
        self.stdout.write(f"  League: {league}")

        # 3. Season
        season, _ = Season.objects.get_or_create(
            league=league,
            year=2026,
            season_type="spring",
            defaults={
                "name": "Spring 2026",
                "start_date": date(2026, 3, 1),
                "end_date": date(2026, 6, 30),
                "is_active": True,
                "registration_open": True,
            },
        )
        self.stdout.write(f"  Season: {season}")

        # 4. Divisions
        divisions_data = [
            ("Majors", 1, True, ["American", "National"]),
            ("AAA", 2, True, ["American", "National"]),
            ("AA", 3, False, []),
            ("A", 4, False, []),
            ("Rookie", 5, False, []),
        ]
        divisions = {}
        for name, order, has_leagues, league_names in divisions_data:
            div, _ = Division.objects.get_or_create(
                league=league,
                name=name,
                defaults={
                    "display_order": order,
                    "has_leagues": has_leagues,
                    "league_names": league_names,
                },
            )
            divisions[name] = div
        self.stdout.write(f"  Divisions: {len(divisions)}")

        # 5. Stations
        stations_data = [
            ("Hitting", HITTING_FIELDS, 1),
            ("Infield", INFIELD_FIELDS, 2),
            ("Outfield", OUTFIELD_FIELDS, 3),
            ("Pitching", PITCHING_FIELDS, 4),
        ]
        for name, fields, order in stations_data:
            Station.objects.get_or_create(
                league=league,
                name=name,
                defaults={
                    "eval_fields": fields,
                    "display_order": order,
                },
            )
        self.stdout.write(f"  Stations: {len(stations_data)}")

        # 6. Teams and TeamSeasons
        team_idx = 0
        team_seasons = {}
        for div_name, div in divisions.items():
            if div.has_leagues:
                # 2 teams per sub-league
                for sub in div.league_names:
                    for _ in range(2):
                        t_name = TEAM_NAMES[team_idx % len(TEAM_NAMES)]
                        team, _ = Team.objects.get_or_create(
                            league=league, name=f"{div_name} {t_name}"
                        )
                        ts, _ = TeamSeason.objects.get_or_create(
                            team=team,
                            season=season,
                            defaults={"division": div, "sub_league": sub},
                        )
                        team_seasons.setdefault(div_name, []).append(ts)
                        team_idx += 1
            else:
                # 2 teams for non-league divisions
                for _ in range(2):
                    t_name = TEAM_NAMES[team_idx % len(TEAM_NAMES)]
                    team, _ = Team.objects.get_or_create(
                        league=league, name=f"{div_name} {t_name}"
                    )
                    ts, _ = TeamSeason.objects.get_or_create(
                        team=team,
                        season=season,
                        defaults={"division": div},
                    )
                    team_seasons.setdefault(div_name, []).append(ts)
                    team_idx += 1
        total_ts = sum(len(v) for v in team_seasons.values())
        self.stdout.write(f"  TeamSeasons: {total_ts}")

        # 7. Coach users + Coach + CoachSeason
        coach_count = 0
        for div_name, ts_list in team_seasons.items():
            for ts in ts_list:
                # Head coach
                hc_email = f'coach.{ts.team.name.lower().replace(" ", ".")}@sfll.org'
                hc_user, created = User.objects.get_or_create(
                    email=hc_email,
                    defaults={
                        "username": hc_email,
                        "first_name": random.choice(FIRST_NAMES),
                        "last_name": random.choice(LAST_NAMES),
                    },
                )
                if created:
                    hc_user.set_password("coach123")
                    hc_user.save()

                coach_obj, _ = Coach.objects.get_or_create(
                    user=hc_user,
                    league=league,
                )
                CoachSeason.objects.get_or_create(
                    coach=coach_obj,
                    team_season=ts,
                    defaults={
                        "season": season,
                        "role": "head_coach",
                        "is_drafter": True,
                    },
                )
                coach_count += 1

                # Assistant coach (50% chance)
                if random.random() > 0.5:
                    ac_email = f'asst.{ts.team.name.lower().replace(" ", ".")}@sfll.org'
                    ac_user, created = User.objects.get_or_create(
                        email=ac_email,
                        defaults={
                            "username": ac_email,
                            "first_name": random.choice(FIRST_NAMES),
                            "last_name": random.choice(LAST_NAMES),
                        },
                    )
                    if created:
                        ac_user.set_password("coach123")
                        ac_user.save()

                    ac_coach, _ = Coach.objects.get_or_create(
                        user=ac_user,
                        league=league,
                    )
                    CoachSeason.objects.get_or_create(
                        coach=ac_coach,
                        team_season=ts,
                        defaults={"season": season, "role": "assistant_coach"},
                    )
                    coach_count += 1
        self.stdout.write(f"  Coaches: {coach_count}")

        # 8. Players + PlayerSeasons
        player_count = 0
        for div_name, div in divisions.items():
            num_players = random.randint(3, 5)
            for _ in range(num_players):
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                sc_id = f"SC-{random.randint(10000, 99999)}"
                player, _ = Player.objects.get_or_create(
                    sportsconnect_player_id=sc_id,
                    defaults={
                        "league": league,
                        "first_name": first,
                        "last_name": last,
                        "date_of_birth": date(2026, 1, 1)
                        - timedelta(days=random.randint(3000, 4500)),
                    },
                )
                ps, _ = PlayerSeason.objects.get_or_create(
                    player=player,
                    season=season,
                    defaults={
                        "division": div,
                        "status": "registered",
                        "account_name": f"{first} {last} Parent",
                        "account_email": f"{first.lower()}.{last.lower()}@example.com",
                    },
                )
                player_count += 1
        self.stdout.write(f"  Players: {player_count}")

        # 9. Sessions + Assignments
        session_count = 0
        for div_name, div in divisions.items():
            for i in range(random.randint(2, 3)):
                ses_date = date(2026, 3, 15) + timedelta(days=i * 7)
                ses, _ = Session.objects.get_or_create(
                    season=season,
                    division=div,
                    date=ses_date,
                    defaults={
                        "name": f"{div_name} SES #{i + 1}",
                        "start_time": time(9, 0),
                        "end_time": time(12, 0),
                        "location": "SFLL Fields",
                    },
                )
                # Assign all players in this division to the session
                for ps in PlayerSeason.objects.filter(season=season, division=div):
                    SessionAssignment.objects.get_or_create(
                        session=ses,
                        player_season=ps,
                        defaults={"assigned_by": admin},
                    )
                session_count += 1
        self.stdout.write(f"  Sessions: {session_count}")

        # 10. Email Templates
        templates_data = [
            (
                "SES Invite",
                "You are invited to {{ session_name }}",
                "Hi {{ parent_name }},\n\n{{ player_name }} is scheduled for {{ session_name }} on {{ date }} at {{ location }}.\n\nPlease RSVP using the link below.\n\n{{ rsvp_link }}",
            ),
            (
                "Makeup Invite",
                "Makeup Session: {{ session_name }}",
                "Hi {{ parent_name }},\n\n{{ player_name }} missed the original session and is invited to the makeup: {{ session_name }} on {{ date }}.\n\n{{ rsvp_link }}",
            ),
            (
                "General Update",
                "{{ subject }}",
                "Hi {{ parent_name }},\n\n{{ body }}\n\nSan Francisco Little League",
            ),
        ]
        for name, subject, body in templates_data:
            EmailTemplate.objects.get_or_create(
                league=league,
                name=name,
                defaults={
                    "subject_template": subject,
                    "body_template": body,
                    "reply_to": "info@sfll.org",
                    "from_name": "San Francisco Little League",
                },
            )
        self.stdout.write(f"  Email Templates: {len(templates_data)}")

        self.stdout.write(self.style.SUCCESS("\nDemo data seeded successfully."))

    def _flush(self):
        """Delete all seeded data (preserving migrations and system tables)."""
        from communications.models import RSVP, EmailLog
        from draft.models import DraftPick, DraftSession
        from evaluations.models import CoachRanking, Evaluation, ObjectiveMetric
        from tryouts.models import CheckIn

        # Delete in dependency order
        CheckIn.objects.all().delete()
        SessionAssignment.objects.all().delete()
        Session.objects.all().delete()
        CoachRanking.objects.all().delete()
        ObjectiveMetric.objects.all().delete()
        Evaluation.objects.all().delete()
        DraftPick.objects.all().delete()
        DraftSession.objects.all().delete()
        RSVP.objects.all().delete()
        EmailLog.objects.all().delete()
        EmailTemplate.objects.all().delete()
        CoachSeason.objects.all().delete()
        Coach.objects.all().delete()
        PlayerSeason.objects.all().delete()
        Player.objects.all().delete()
        TeamSeason.objects.all().delete()
        Team.objects.all().delete()
        Station.objects.all().delete()
        Division.objects.all().delete()
        Season.objects.all().delete()
        League.objects.all().delete()
        User.objects.filter(email__endswith="@sfll.org").delete()
        self.stdout.write("  All demo data flushed.")
