import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template import Template, Context

from players.models import Division, PlayerSeason, Season, TeamSeason
from tryouts.models import Session
from .forms import EmailTemplateForm
from .models import EmailLog, EmailTemplate, RSVP

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _can_manage_comms(user):
    """Check if user has CTO or Comms Editor role."""
    if user.is_superuser:
        return True
    return user.roles.filter(
        is_active=True,
        role__in=['cto', 'comms_editor'],
    ).exists()


def _get_active_season():
    """Return the current active season or None."""
    return Season.objects.filter(is_active=True).first()


def _get_sample_context():
    """Build sample merge-field context for template previewing."""
    return {
        'player': type('Player', (), {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'full_name': 'Jane Smith',
        })(),
        'session': type('Session', (), {
            'name': 'Majors SES Session 1',
            'date': '2026-03-28',
            'start_time': '9:00 AM',
            'end_time': '11:00 AM',
            'location': 'Field 3',
        })(),
        'season': type('Season', (), {
            'name': 'Spring 2026',
            'year': 2026,
        })(),
        'division': type('Division', (), {
            'name': 'Majors',
        })(),
        'rsvp_url': 'https://sfll.example.com/rsvp/sample-token/',
        'account_name': 'John Smith',
        'league_name': 'San Francisco Little League',
    }


# ---------------------------------------------------------------------------
# Comms Home (SFLL-80)
# ---------------------------------------------------------------------------

@login_required
def comms_home(request):
    """Communications hub — links to templates, compose, log, RSVP dashboard."""
    if not _can_manage_comms(request.user):
        return HttpResponseForbidden("You do not have permission to access communications.")

    template_count = EmailTemplate.objects.filter(is_active=True).count()
    email_count = EmailLog.objects.count()
    recent_emails = EmailLog.objects.select_related('template', 'sent_by')[:5]

    # RSVP summary for active season
    active_season = _get_active_season()
    rsvp_count = 0
    if active_season:
        rsvp_count = RSVP.objects.filter(
            session__season=active_season,
        ).count()

    return render(request, 'communications/comms_home.html', {
        'template_count': template_count,
        'email_count': email_count,
        'recent_emails': recent_emails,
        'rsvp_count': rsvp_count,
    })


# ---------------------------------------------------------------------------
# Template CRUD (SFLL-77)
# ---------------------------------------------------------------------------

@login_required
def template_list(request):
    """List all email templates."""
    if not _can_manage_comms(request.user):
        return HttpResponseForbidden("You do not have permission to manage templates.")

    templates = EmailTemplate.objects.all().order_by('-is_active', 'name')

    return render(request, 'communications/template_list.html', {
        'templates': templates,
    })


@login_required
def template_create(request):
    """Create a new email template."""
    if not _can_manage_comms(request.user):
        return HttpResponseForbidden("You do not have permission to create templates.")

    active_season = _get_active_season()
    if not active_season:
        messages.error(request, "No active season. Cannot create a template without a league context.")
        return redirect('communications:template_list')

    if request.method == 'POST':
        form = EmailTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.league = active_season.league
            template.save()
            messages.success(request, f'Template "{template.name}" created.')
            return redirect('communications:template_list')
    else:
        form = EmailTemplateForm()

    return render(request, 'communications/template_form.html', {
        'form': form,
        'is_edit': False,
    })


@login_required
def template_edit(request, pk):
    """Edit an existing email template."""
    if not _can_manage_comms(request.user):
        return HttpResponseForbidden("You do not have permission to edit templates.")

    template = get_object_or_404(EmailTemplate, pk=pk)

    if request.method == 'POST':
        form = EmailTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, f'Template "{template.name}" updated.')
            return redirect('communications:template_list')
    else:
        form = EmailTemplateForm(instance=template)

    return render(request, 'communications/template_form.html', {
        'form': form,
        'template': template,
        'is_edit': True,
    })


@login_required
def template_preview(request, pk):
    """Preview an email template with sample data."""
    if not _can_manage_comms(request.user):
        return HttpResponseForbidden("You do not have permission to preview templates.")

    email_template = get_object_or_404(EmailTemplate, pk=pk)
    sample = _get_sample_context()

    try:
        rendered_subject = Template(email_template.subject_template).render(Context(sample))
        rendered_body = Template(email_template.body_template).render(Context(sample))
    except Exception as e:
        rendered_subject = f"[Template Error: {e}]"
        rendered_body = f"[Template Error: {e}]"

    return render(request, 'communications/template_preview.html', {
        'email_template': email_template,
        'rendered_subject': rendered_subject,
        'rendered_body': rendered_body,
        'sample': sample,
    })


# ---------------------------------------------------------------------------
# Bulk Email Send (SFLL-78)
# ---------------------------------------------------------------------------

def _build_recipient_queryset(request):
    """Build a PlayerSeason queryset from filter parameters."""
    active_season = _get_active_season()
    if not active_season:
        return PlayerSeason.objects.none()

    qs = PlayerSeason.objects.select_related(
        'player', 'division', 'assigned_team__team',
    ).filter(season=active_season)

    division_id = request.POST.get('division') or request.GET.get('division')
    if division_id:
        qs = qs.filter(division_id=division_id)

    session_id = request.POST.get('session') or request.GET.get('session')
    if session_id:
        qs = qs.filter(session_assignments__session_id=session_id).distinct()

    status = request.POST.get('status') or request.GET.get('status')
    if status:
        qs = qs.filter(status=status)

    team_id = request.POST.get('team') or request.GET.get('team')
    if team_id:
        qs = qs.filter(assigned_team_id=team_id)

    return qs.order_by('player__last_name', 'player__first_name')


@login_required
def compose_send(request):
    """Compose and send a bulk email — select template and recipients."""
    if not _can_manage_comms(request.user):
        return HttpResponseForbidden("You do not have permission to send emails.")

    active_season = _get_active_season()
    if not active_season:
        messages.error(request, "No active season configured.")
        return redirect('communications:index')

    templates = EmailTemplate.objects.filter(is_active=True).order_by('name')
    divisions = Division.objects.filter(
        league=active_season.league, is_active=True,
    ).order_by('display_order')
    sessions = Session.objects.filter(season=active_season).order_by('date', 'start_time')
    teams = TeamSeason.objects.select_related('team').filter(
        season=active_season,
    ).order_by('team__name')

    # If filtering, show count
    recipient_count = None
    if request.GET:
        recipients = _build_recipient_queryset(request)
        recipient_count = recipients.count()

    return render(request, 'communications/compose.html', {
        'templates': templates,
        'divisions': divisions,
        'sessions': sessions,
        'teams': teams,
        'recipient_count': recipient_count,
        'filter_params': request.GET,
    })


@login_required
def send_preview(request):
    """Preview the first email and full recipient list before sending."""
    if not _can_manage_comms(request.user):
        return HttpResponseForbidden("You do not have permission to send emails.")

    template_id = request.POST.get('template')
    if not template_id:
        messages.error(request, "Please select a template.")
        return redirect('communications:compose')

    email_template = get_object_or_404(EmailTemplate, pk=template_id, is_active=True)
    recipients = _build_recipient_queryset(request)

    if not recipients.exists():
        messages.error(request, "No recipients match your filters.")
        return redirect('communications:compose')

    # Preview with the first recipient
    first = recipients.first()
    context = _build_player_context(first)

    try:
        rendered_subject = Template(email_template.subject_template).render(Context(context))
        rendered_body = Template(email_template.body_template).render(Context(context))
    except Exception as e:
        rendered_subject = f"[Template Error: {e}]"
        rendered_body = f"[Template Error: {e}]"

    return render(request, 'communications/send_preview.html', {
        'email_template': email_template,
        'rendered_subject': rendered_subject,
        'rendered_body': rendered_body,
        'first_recipient': first,
        'recipients': recipients,
        'recipient_count': recipients.count(),
        'filter_params': request.POST,
    })


@login_required
def send_confirm(request):
    """Confirm and dispatch bulk email send."""
    if not _can_manage_comms(request.user):
        return HttpResponseForbidden("You do not have permission to send emails.")

    if request.method != 'POST':
        return redirect('communications:compose')

    template_id = request.POST.get('template')
    email_template = get_object_or_404(EmailTemplate, pk=template_id)
    recipients = _build_recipient_queryset(request)

    if not recipients.exists():
        messages.error(request, "No recipients to send to.")
        return redirect('communications:compose')

    player_season_ids = list(recipients.values_list('id', flat=True))

    # Dispatch Celery task
    from core.tasks import send_bulk_email
    send_bulk_email.delay(email_template.id, player_season_ids, request.user.id)

    messages.success(
        request,
        f"Sending {len(player_season_ids)} email(s) using \"{email_template.name}\". "
        f"Check the email log for delivery status.",
    )

    return render(request, 'communications/send_confirm.html', {
        'email_template': email_template,
        'recipient_count': len(player_season_ids),
    })


def _build_player_context(player_season):
    """Build a template context dict for a PlayerSeason."""
    ps = player_season
    player = ps.player
    division = ps.division

    # Try to find an upcoming session assignment
    session = None
    assignment = ps.session_assignments.select_related('session').order_by(
        'session__date',
    ).first()
    if assignment:
        session = assignment.session

    rsvp_url = ''
    if session:
        from django.urls import reverse
        rsvp_url = reverse('public_rsvp', kwargs={'token': ps.rsvp_token})

    return {
        'player': player,
        'player_season': ps,
        'season': ps.season,
        'division': division,
        'session': session,
        'rsvp_url': rsvp_url,
        'account_name': ps.account_name,
        'league_name': ps.season.league.name if ps.season else 'SFLL',
    }


# ---------------------------------------------------------------------------
# Public RSVP (SFLL-79)
# ---------------------------------------------------------------------------

def public_rsvp(request, token):
    """Public RSVP page — no authentication required."""
    player_season = get_object_or_404(
        PlayerSeason.objects.select_related('player', 'season', 'division'),
        rsvp_token=token,
    )

    # Find the next upcoming session assignment for this player
    assignment = player_season.session_assignments.select_related(
        'session', 'session__division',
    ).order_by('session__date').first()

    if not assignment:
        return render(request, 'communications/public_rsvp.html', {
            'player': player_season.player,
            'error': 'No SES session found for this player. Please contact the league.',
        })

    session = assignment.session
    existing_rsvp = RSVP.objects.filter(
        player_season=player_season,
        session=session,
    ).first()

    if request.method == 'POST':
        status = request.POST.get('status')
        if status not in ('attending', 'not_attending', 'maybe'):
            messages.error(request, "Invalid RSVP response.")
            return redirect('public_rsvp', token=token)

        rsvp, created = RSVP.objects.update_or_create(
            player_season=player_season,
            session=session,
            defaults={
                'status': status,
                'response_method': 'web',
                'ip_address': request.META.get('REMOTE_ADDR'),
            },
        )

        return render(request, 'communications/public_rsvp.html', {
            'player': player_season.player,
            'session': session,
            'rsvp': rsvp,
            'confirmed': True,
        })

    return render(request, 'communications/public_rsvp.html', {
        'player': player_season.player,
        'session': session,
        'existing_rsvp': existing_rsvp,
    })


# ---------------------------------------------------------------------------
# Email Log (SFLL-80)
# ---------------------------------------------------------------------------

@login_required
def email_log(request):
    """View sent email log with filters."""
    if not _can_manage_comms(request.user):
        return HttpResponseForbidden("You do not have permission to view the email log.")

    emails = EmailLog.objects.select_related(
        'template', 'sent_by', 'player_season__player',
    ).order_by('-sent_at')

    # Filters
    template_id = request.GET.get('template')
    if template_id:
        emails = emails.filter(template_id=template_id)

    date_from = request.GET.get('date_from')
    if date_from:
        emails = emails.filter(sent_at__date__gte=date_from)

    date_to = request.GET.get('date_to')
    if date_to:
        emails = emails.filter(sent_at__date__lte=date_to)

    templates = EmailTemplate.objects.all().order_by('name')

    return render(request, 'communications/email_log.html', {
        'emails': emails[:200],
        'templates': templates,
        'filter_template': template_id,
        'filter_date_from': date_from or '',
        'filter_date_to': date_to or '',
    })


# ---------------------------------------------------------------------------
# RSVP Dashboard (SFLL-80)
# ---------------------------------------------------------------------------

@login_required
def rsvp_dashboard(request):
    """RSVP dashboard — per-session response rates and management."""
    if not _can_manage_comms(request.user):
        return HttpResponseForbidden("You do not have permission to view the RSVP dashboard.")

    active_season = _get_active_season()
    if not active_season:
        return render(request, 'communications/rsvp_dashboard.html', {
            'session_data': [],
            'no_season': True,
        })

    sessions = Session.objects.filter(
        season=active_season,
    ).select_related('division').order_by('date', 'start_time')

    session_data = []
    for session in sessions:
        total_assigned = session.assignments.count()
        rsvps = RSVP.objects.filter(session=session)
        attending = rsvps.filter(status='attending').count()
        not_attending = rsvps.filter(status='not_attending').count()
        maybe = rsvps.filter(status='maybe').count()
        responded = attending + not_attending + maybe
        no_response = total_assigned - responded if total_assigned > responded else 0
        response_rate = (responded / total_assigned * 100) if total_assigned > 0 else 0

        session_data.append({
            'session': session,
            'total_assigned': total_assigned,
            'attending': attending,
            'not_attending': not_attending,
            'maybe': maybe,
            'no_response': no_response,
            'response_rate': round(response_rate),
        })

    # Overall stats
    total_rsvps = RSVP.objects.filter(session__season=active_season).count()
    total_attending = RSVP.objects.filter(session__season=active_season, status='attending').count()

    return render(request, 'communications/rsvp_dashboard.html', {
        'session_data': session_data,
        'total_rsvps': total_rsvps,
        'total_attending': total_attending,
    })
