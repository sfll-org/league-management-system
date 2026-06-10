from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Coach, CoachSeason, UserRole
from communications.models import RSVP
from core.models import AuditLog, ImportRun
from draft.models import DraftPick, DraftSession
from evaluations.models import Evaluation
from players.models import (Division, PlayerSeason, Season, Station, Team,
                            TeamSeason)
from tryouts.models import CheckIn, Session, SessionAssignment


def _get_user_roles(user):
    """Return a set of role strings for the user."""
    if user.is_superuser:
        return {"cto"}
    return set(
        UserRole.objects.filter(user=user, is_active=True).values_list(
            "role", flat=True
        )
    )


def _is_admin(roles):
    """Return True if user has an admin-level role."""
    return bool(roles & {"cto", "ses_manager", "vp_player_agents", "president"})


def _is_coach(roles):
    """Return True if user has a coach role."""
    return bool(roles & {"head_coach", "assistant_coach"})


def _is_front_desk(roles):
    """Return True if user has the front desk role."""
    return "front_desk" in roles


@login_required
def dashboard(request):
    """Main dashboard with role-appropriate widgets."""
    active_season = Season.objects.filter(is_active=True).first()
    roles = _get_user_roles(request.user)

    context = {
        "season": active_season,
        "roles": roles,
        "is_admin": _is_admin(roles),
        "is_coach": _is_coach(roles),
        "is_front_desk": _is_front_desk(roles),
        "player_count": 0,
        "session_count": 0,
        "eval_count": 0,
        "draft_status": "No active season",
    }

    if not active_season:
        return render(request, "dashboard.html", context)

    # ------- Shared stats -------
    player_seasons = PlayerSeason.objects.filter(season=active_season)
    sessions = Session.objects.filter(season=active_season)
    evaluations = Evaluation.objects.filter(session__season=active_season)

    context["player_count"] = player_seasons.count()
    context["session_count"] = sessions.count()
    context["eval_count"] = evaluations.count()
    context["draft_status"] = "Complete" if active_season.draft_complete else "Pending"

    # ------- Admin widgets -------
    if _is_admin(roles):
        # Player counts by division
        division_counts = (
            player_seasons.values("division__name")
            .annotate(count=Count("id"))
            .order_by("division__display_order")
        )
        context["division_counts"] = division_counts

        # Registration status
        context["registration_open"] = active_season.registration_open

        # SES session stats
        today = timezone.now().date()
        upcoming_sessions = sessions.filter(date__gte=today)
        context["upcoming_session_count"] = upcoming_sessions.count()

        # RSVP rates
        total_assignments = SessionAssignment.objects.filter(
            session__season=active_season
        ).count()
        total_rsvps = RSVP.objects.filter(session__season=active_season).count()
        context["rsvp_rate"] = round(
            (total_rsvps / total_assignments * 100) if total_assignments > 0 else 0
        )

        # Check-in rates
        total_checkins = CheckIn.objects.filter(
            session_assignment__session__season=active_season
        ).count()
        context["checkin_rate"] = round(
            (total_checkins / total_assignments * 100) if total_assignments > 0 else 0
        )

        # Evaluation completion
        coaches_evaluated = evaluations.values("coach_season").distinct().count()
        players_evaluated = evaluations.values("player_season").distinct().count()
        context["coaches_evaluated"] = coaches_evaluated
        context["players_evaluated"] = players_evaluated

        # Draft status per division
        draft_sessions = DraftSession.objects.filter(
            season=active_season
        ).select_related("division")
        context["draft_sessions"] = draft_sessions

        # SportsConnect: last sync time + flagged records
        last_import = ImportRun.objects.order_by("-started_at").first()
        context["last_import"] = last_import
        if last_import:
            context["flagged_count"] = last_import.flagged_for_review

        # Recent audit log entries
        context["recent_audit"] = AuditLog.objects.select_related("user")[:10]

        # Next upcoming sessions for the dashboard preview
        context["admin_upcoming_sessions"] = upcoming_sessions.select_related(
            "division"
        ).order_by("date", "start_time")[:4]

        # Top draft picks for the dashboard preview
        context["top_picks"] = (
            DraftPick.objects.filter(draft_session__season=active_season)
            .select_related("player_season__player", "team_season__team")
            .order_by("pick_number")[:5]
        )

        # Attention inbox items derived from live data
        attention = []
        if last_import and last_import.flagged_for_review:
            attention.append(
                {
                    "level": "danger" if last_import.flagged_for_review > 5 else "warn",
                    "title": f'{last_import.flagged_for_review} flagged SportsConnect record{"s" if last_import.flagged_for_review != 1 else ""}',
                    "sub": "Review before next import run",
                    "meta": f'{last_import.started_at.strftime("%-I:%M") if last_import else "—"}',
                    "url": "import_history",
                }
            )
        rsvp_val = context.get("rsvp_rate", 100)
        if rsvp_val < 75:
            attention.append(
                {
                    "level": "warn",
                    "title": f"RSVP rate at {rsvp_val}%",
                    "sub": "Send reminders to lift participation",
                    "meta": "—",
                    "url": None,
                }
            )
        for ds in draft_sessions:
            if ds.status == "drafting":
                attention.append(
                    {
                        "level": "info",
                        "title": f"{ds.division.name} draft in progress",
                        "sub": f"Round {ds.current_round} · pick {ds.current_pick}",
                        "meta": "now",
                        "url": "draft:index",
                    }
                )
        context["attention_items"] = attention
        counts = {"danger": 0, "warn": 0, "info": 0}
        for item in attention:
            counts[item["level"]] = counts.get(item["level"], 0) + 1
        context["attention_counts"] = counts

    # ------- Coach widgets -------
    if _is_coach(roles):
        try:
            coach = Coach.objects.get(user=request.user)
            coach_season = (
                CoachSeason.objects.filter(coach=coach, season=active_season)
                .select_related(
                    "team_season", "team_season__team", "team_season__division"
                )
                .first()
            )
            context["coach_season"] = coach_season

            if coach_season:
                # Team info
                context["team_players"] = PlayerSeason.objects.filter(
                    assigned_team=coach_season.team_season
                ).select_related("player")

                # Upcoming sessions for their division
                today = timezone.now().date()
                context["coach_upcoming_sessions"] = Session.objects.filter(
                    season=active_season,
                    division=coach_season.team_season.division,
                    date__gte=today,
                )[:5]

                # Evaluation progress
                context["coach_eval_count"] = Evaluation.objects.filter(
                    coach_season=coach_season,
                    session__season=active_season,
                ).count()

                total_players_in_division = PlayerSeason.objects.filter(
                    season=active_season,
                    division=coach_season.team_season.division,
                ).count()
                context["division_player_count"] = total_players_in_division

        except Coach.DoesNotExist:
            context["coach_season"] = None

    # ------- Front Desk widgets -------
    if _is_front_desk(roles):
        today = timezone.now().date()
        context["todays_sessions"] = sessions.filter(date=today).select_related(
            "division"
        )

    return render(request, "dashboard.html", context)


def _build_attention_items(active_season):
    """Build the attention-inbox item list for the given season.

    Returns a list of dicts with keys: type (blocker|warning|today), label, url.
    Each item maps directly to what the _partials/dashboard_inbox.html template expects.
    """
    from django.urls import reverse

    items = []

    # Flagged SportsConnect records
    last_import = ImportRun.objects.order_by('-started_at').first()
    if last_import and last_import.flagged_for_review:
        n = last_import.flagged_for_review
        items.append({
            'type': 'blocker' if n > 5 else 'warning',
            'label': f'{n} flagged SportsConnect record{"s" if n != 1 else ""} — review before next import',
            'url': reverse('import_history'),
        })

    # RSVP participation rate
    total_assignments = SessionAssignment.objects.filter(
        session__season=active_season
    ).count()
    if total_assignments:
        total_rsvps = RSVP.objects.filter(session__season=active_season).count()
        rsvp_rate = round(total_rsvps / total_assignments * 100)
        if rsvp_rate < 75:
            items.append({
                'type': 'warning',
                'label': f'RSVP rate at {rsvp_rate}% — send reminders to lift participation',
                'url': None,
            })

    # Active draft sessions
    draft_sessions = DraftSession.objects.filter(
        season=active_season, status='drafting'
    ).select_related('division')
    for ds in draft_sessions:
        items.append({
            'type': 'today',
            'label': f'{ds.division.name} draft in progress — round {ds.current_round}, pick {ds.current_pick}',
            'url': reverse('draft:index'),
        })

    return items


@login_required
def dashboard_inbox(request):
    """HTMX partial: filtered 'Needs attention' inbox for admins."""
    from django.http import HttpResponseForbidden
    roles = _get_user_roles(request.user)
    if not _is_admin(roles):
        return HttpResponseForbidden()

    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        return render(request, '_partials/dashboard_inbox.html', {
            'attention_items': [],
            'attention_filter': 'all',
        })

    all_items = _build_attention_items(active_season)
    active_filter = request.GET.get('filter', 'all')

    if active_filter == 'blockers':
        items = [i for i in all_items if i['type'] == 'blocker']
    elif active_filter == 'warnings':
        items = [i for i in all_items if i['type'] == 'warning']
    elif active_filter == 'today':
        items = [i for i in all_items if i['type'] == 'today']
    else:
        items = all_items

    return render(request, '_partials/dashboard_inbox.html', {
        'attention_items': items,
        'attention_filter': active_filter,
    })


def health_check(request):
    """Health check endpoint for Docker / load balancers."""
    return JsonResponse({"status": "ok"})


# --- SFLL-117: ⌘K command palette search endpoint -------------------------

# Static page registry keyed by minimum role. The view filters by what the
# current user can reach, then ranks against the query client-side.
_CMDK_PAGES = (
    # (title, url_name, kind, role_required)
    ('Dashboard',      'dashboard',                'page',  None),
    ('Roster',         'players:index',            'page',  None),
    ('Teams',          'players:teams',            'page',  None),
    ('Communications', 'communications:index',     'page',  None),
    ('SES Sessions',   'tryouts:index',            'page',  None),
    ('Evaluations',    'evaluations:index',        'page',  None),
    ('Draft',          'draft:index',              'page',  None),
    ('Imports',        'import_history',           'admin', 'admin'),
    ('Configuration',  'config_home',              'admin', 'admin'),
    ('Audit log',      'audit_log',                'admin', 'admin'),
    ('User management', 'user_list',               'admin', 'admin'),
)


def _cmdk_pages(is_admin):
    from django.urls import NoReverseMatch, reverse
    out = []
    for title, name, kind, required in _CMDK_PAGES:
        if required == 'admin' and not is_admin:
            continue
        try:
            url = reverse(name)
        except NoReverseMatch:
            continue
        out.append({'title': title, 'url': url, 'kind': kind})
    return out


def _cmdk_players(query, limit=20):
    """Return players matching `query`. Empty query yields a recent slice."""
    from django.urls import NoReverseMatch, reverse
    season = Season.objects.filter(is_active=True).first()
    qs = PlayerSeason.objects.select_related(
        'player', 'division', 'assigned_team__team'
    )
    if season:
        qs = qs.filter(season=season)
    if query:
        qs = qs.filter(
            Q(player__first_name__icontains=query)
            | Q(player__last_name__icontains=query)
        )
    qs = qs.order_by('player__last_name', 'player__first_name')[:limit]

    try:
        roster_url = reverse('players:index')
    except NoReverseMatch:
        roster_url = '/players/'

    items = []
    for ps in qs:
        player = ps.player
        name = f'{player.last_name}, {player.first_name}'.strip(', ')
        sub_bits = []
        if ps.division_id and ps.division:
            sub_bits.append(ps.division.name)
        if ps.assigned_team_id and ps.assigned_team and ps.assigned_team.team:
            sub_bits.append(ps.assigned_team.team.name)
        items.append({
            'title': name or player.first_name or player.last_name or 'Unnamed player',
            'subtitle': ' · '.join(sub_bits),
            'url': f'{roster_url}?{urlencode({"q": name})}',
            'kind': 'player',
        })
    return items


def _cmdk_families(query, limit=15):
    """Return distinct PlayerSeason.account_name values matching the query.

    Family Detail (Phase 5 / SFLL-110) isn't merged yet; for now we deep-link
    into the roster filtered by the account name so the palette is useful
    today. Update the URL when family-detail lands.
    """
    from django.urls import NoReverseMatch, reverse
    season = Season.objects.filter(is_active=True).first()
    qs = PlayerSeason.objects.exclude(account_name='')
    if season:
        qs = qs.filter(season=season)
    if query:
        qs = qs.filter(account_name__icontains=query)

    rows = (
        qs.values('account_name')
        .annotate(player_count=Count('id'))
        .order_by('account_name')[:limit]
    )

    try:
        roster_url = reverse('players:index')
    except NoReverseMatch:
        roster_url = '/players/'

    items = []
    for row in rows:
        name = row['account_name']
        count = row['player_count']
        suffix = 'player' if count == 1 else 'players'
        items.append({
            'title': name,
            'subtitle': f'{count} {suffix}',
            'url': f'{roster_url}?{urlencode({"account": name})}',
            'kind': 'family',
        })
    return items


@login_required
def cmdk_search(request):
    """SFLL-117 — JSON search backend for the ⌘K command palette.

    Pages are role-filtered against the requester; players and families are
    queried per session against the active season. Empty `q` returns a small
    starter slice so the palette is useful on first open.
    """
    if not getattr(request.user, 'power_user_mode', False):
        # Feature flag is per-user; non-power-users shouldn't be able to
        # probe roster names via this endpoint.
        return JsonResponse({'detail': 'Not enabled.'}, status=403)

    query = (request.GET.get('q') or '').strip()
    roles = _get_user_roles(request.user)
    is_admin = _is_admin(roles)

    return JsonResponse({
        'pages': _cmdk_pages(is_admin),
        'players': _cmdk_players(query),
        'families': _cmdk_families(query),
    })
