"""
Celery tasks for scheduled SportsConnect sync and bulk email.

The primary task, sync_sportsconnect, fetches the CSV from each league's
configured report URL and runs the SportsConnectImporter. It is safe to
call multiple times (idempotent) — the importer uses get_or_create and
delta detection internally.

Schedule configuration:
    Configure via Django admin -> Periodic Tasks (django-celery-beat).
    Recommended: IntervalSchedule of 60 minutes, task name
    "core.tasks.sync_sportsconnect".
"""

import io
import logging

import requests
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_sportsconnect(self, league_id=None):
    """Fetch SportsConnect CSV from configured URL and run import.

    If league_id is None, syncs all leagues with a configured report URL.
    """
    from core.importers import SportsConnectImporter
    from players.models import League, Season

    if league_id:
        leagues = League.objects.filter(pk=league_id)
    else:
        leagues = League.objects.exclude(sportsconnect_report_url="")

    for league in leagues:
        if not league.sportsconnect_report_url:
            logger.info("Skipping %s — no SportsConnect URL configured", league.name)
            continue

        try:
            # Download the CSV
            response = requests.get(league.sportsconnect_report_url, timeout=60)
            response.raise_for_status()

            # Find active season
            season = Season.objects.filter(league=league, is_active=True).first()
            if not season:
                logger.warning("No active season for %s — skipping", league.name)
                continue

            # Run import
            csv_file = io.StringIO(response.text)
            importer = SportsConnectImporter(league=league, season=season)
            import_run = importer.run(csv_file)

            logger.info(
                "SportsConnect sync for %s: "
                "%d new players, %d new seasons, %d updates, "
                "%d flags, %d errors",
                league.name,
                import_run.new_players,
                import_run.new_player_seasons,
                import_run.updated_records,
                import_run.flagged_for_review,
                import_run.errors,
            )
        except requests.RequestException as e:
            logger.error("Failed to fetch SportsConnect CSV for %s: %s", league.name, e)
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=60 * (self.request.retries + 1))
        except Exception:
            logger.exception("SportsConnect sync failed for %s", league.name)


@shared_task(bind=True, max_retries=3)
def send_bulk_email(self, template_id, player_season_ids, sent_by_id):
    """Send templated email to a list of players.

    For each PlayerSeason:
      - Render template with player context
      - Send via Django email backend
      - Create EmailLog record
    """
    from django.core.mail import send_mail
    from django.template import Context, Template
    from django.urls import reverse

    from accounts.models import User
    from communications.models import EmailLog, EmailTemplate
    from players.models import PlayerSeason

    email_template = EmailTemplate.objects.get(pk=template_id)
    sent_by = User.objects.filter(pk=sent_by_id).first()
    player_seasons = PlayerSeason.objects.select_related(
        "player",
        "season",
        "season__league",
        "division",
    ).filter(pk__in=player_season_ids)

    success_count = 0
    error_count = 0

    for ps in player_seasons:
        # Skip players without an email address
        to_email = ps.account_email
        if not to_email:
            logger.warning(
                "Skipping %s — no account_email on PlayerSeason %d",
                ps.player.full_name,
                ps.pk,
            )
            continue

        # Build context
        player = ps.player
        division = ps.division
        session = None
        assignment = (
            ps.session_assignments.select_related("session")
            .order_by(
                "session__date",
            )
            .first()
        )
        if assignment:
            session = assignment.session

        rsvp_url = ""
        try:
            rsvp_url = reverse("public_rsvp", kwargs={"token": ps.rsvp_token})
        except Exception:
            pass

        context = Context(
            {
                "player": player,
                "player_season": ps,
                "season": ps.season,
                "division": division,
                "session": session,
                "rsvp_url": rsvp_url,
                "account_name": ps.account_name,
                "league_name": ps.season.league.name if ps.season else "SFLL",
            }
        )

        try:
            rendered_subject = Template(email_template.subject_template).render(context)
            rendered_body = Template(email_template.body_template).render(context)

            from_email = None
            if email_template.from_name:
                from_email = f"{email_template.from_name} <noreply@sfll.org>"

            # Gather CC addresses
            cc = []
            if ps.additional_email:
                cc.append(ps.additional_email)

            send_mail(
                subject=rendered_subject,
                message=rendered_body,
                from_email=from_email,
                recipient_list=[to_email],
                fail_silently=False,
            )

            # Create log record
            EmailLog.objects.create(
                player_season=ps,
                template=email_template,
                to_address=to_email,
                cc_addresses=cc,
                subject=rendered_subject,
                body_snapshot=rendered_body,
                sent_by=sent_by,
            )

            success_count += 1

        except Exception as e:
            error_count += 1
            logger.error(
                "Failed to send email to %s (PlayerSeason %d): %s",
                to_email,
                ps.pk,
                e,
            )

            # Still log the attempt with bounce info
            EmailLog.objects.create(
                player_season=ps,
                template=email_template,
                to_address=to_email,
                subject=f"[FAILED] {email_template.subject_template[:100]}",
                body_snapshot=str(e),
                sent_by=sent_by,
                bounced=True,
                bounce_reason=str(e),
            )

    logger.info(
        "Bulk email complete for template '%s': %d sent, %d errors",
        email_template.name,
        success_count,
        error_count,
    )
