from collections import Counter

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from accounts.models import CoachSeason
from tryouts.models import Session

from .models import Division, PlayerSeason, Season, TeamSeason


@login_required
def index(request):
    """Roster — Pacific token-driven list with division chips, sub-league /
    Top-4 / Unassigned view toggle, and name search.

    Honours `?q=<name>` (plain or 'Last, First' format) and `?account=<account_name>`
    so the SFLL-117 ⌘K palette can deep-link into a filtered view.
    """
    active_season = Season.objects.filter(is_active=True).first()

    qs = (
        PlayerSeason.objects
        .select_related('player', 'division', 'assigned_team__team')
        .filter(season=active_season)
        if active_season
        else PlayerSeason.objects.none()
    )

    divisions = list(Division.objects.filter(is_active=True))

    division_param = request.GET.get('division', '')
    selected_division = next(
        (d for d in divisions if str(d.id) == division_param), None,
    )
    if selected_division:
        qs = qs.filter(division=selected_division)

    sub_leagues = (
        list(selected_division.league_names)
        if selected_division and selected_division.has_leagues
        else []
    )
    league_param = request.GET.get('league', '')
    if league_param and league_param in sub_leagues:
        qs = qs.filter(assigned_team__sub_league=league_param)

    view_param = request.GET.get('view', 'all')
    if view_param == 'top4':
        qs = qs.filter(is_top_4=True)
    elif view_param == 'unassigned':
        qs = qs.filter(assigned_team__isnull=True)
    else:
        view_param = 'all'

    q = (request.GET.get('q') or '').strip()
    account = (request.GET.get('account') or '').strip()
    if q:
        if ',' in q:
            # "Last, First" format produced by the command-palette deep-links.
            last_part, _, first_part = q.partition(',')
            qs = qs.filter(
                Q(player__last_name__icontains=last_part.strip())
                & Q(player__first_name__icontains=first_part.strip())
            )
        else:
            qs = qs.filter(
                Q(player__first_name__icontains=q)
                | Q(player__last_name__icontains=q)
            )
    if account:
        qs = qs.filter(account_name=account)

    return render(request, 'players/index.html', {
        'player_seasons': qs,
        'season': active_season,
        'divisions': divisions,
        'sub_leagues': sub_leagues,
        'selected_division': selected_division,
        'selected_league': league_param if league_param in sub_leagues else '',
        'view': view_param,
        'q': q,
        'roster_query': q,
        'roster_account': account,
    })


@login_required
def teams(request):
    """Team list for the active season."""
    active_season = Season.objects.filter(is_active=True).first()
    team_seasons = TeamSeason.objects.select_related(
        'team', 'division',
    ).filter(season=active_season) if active_season else TeamSeason.objects.none()

    return render(request, 'players/teams.html', {
        'team_seasons': team_seasons,
        'season': active_season,
    })


@login_required
def dugout_card(request, pk):
    """Printable half-sheet dugout card for a single TeamSeason.

    Schedule + per-player emergency phones are blank fill-in rows: SFLL
    doesn't store games or guardian phone numbers yet, and coaches who
    actually print this expect to ink those in field-side.
    """
    team_season = get_object_or_404(
        TeamSeason.objects.select_related('team', 'division', 'season'),
        pk=pk,
    )
    roster = (
        PlayerSeason.objects
        .select_related('player')
        .filter(assigned_team=team_season)
        .order_by('player__last_name', 'player__first_name')
    )

    return render(request, 'players/dugout_card.html', {
        'team_season': team_season,
        'roster': roster,
        'schedule_slots': range(5),
    })


# ── Print surfaces — SFLL-114 (Phase 9) ────────────────────────────────────


@login_required
def print_index(request):
    """Index listing every team in the active season with a Print card link.

    Grouped by division + sub-league so a manager can scan quickly before
    a game day. Lives at /players/print/ alongside the other roster surfaces.
    """
    active_season = Season.objects.filter(is_active=True).first()
    team_seasons = (
        TeamSeason.objects
        .select_related('team', 'division')
        .filter(season=active_season)
        .order_by('division__display_order', 'sub_league', 'team__name')
        if active_season
        else TeamSeason.objects.none()
    )
    return render(request, 'players/print_index.html', {
        'team_seasons': team_seasons,
        'season': active_season,
    })


@login_required
def print_dugout_card(request, team_season_id):
    """Half-sheet dugout roster card — standalone print surface.

    Renders a print-only page (no app shell) with two identical half-sheet
    cards stacked on one letter sheet. The browser print dialog fires on
    load; pass ?print=0 to suppress when proofing layout on screen.

    Each card carries:
    - Team strip: team name + division + head/assistant coaches with phone
    - Next 5 sessions in the team's division (stand-in for a Game model)
    - Roster with parent/guardian name + emergency contact emails
    """
    team_season = get_object_or_404(
        TeamSeason.objects.select_related('team__league', 'season__league', 'division'),
        pk=team_season_id,
    )

    coach_seasons = list(
        CoachSeason.objects
        .filter(team_season=team_season)
        .select_related('coach__user')
        .order_by('role', 'coach__user__last_name')
    )
    head_coach = next((cs for cs in coach_seasons if cs.role == 'head_coach'), None)
    assistant_coaches = [cs for cs in coach_seasons if cs.role == 'assistant_coach']

    roster = list(
        PlayerSeason.objects
        .filter(assigned_team=team_season)
        .select_related('player')
        .order_by('player__last_name', 'player__first_name')
    )

    # Sessions stand in for a Game model until that lands — same placeholder
    # pattern Phase 8 used. Filter to the team's division, current season,
    # future-only, limit to the next 5. Season filter prevents sessions from
    # other seasons sharing the same division from leaking onto the card.
    today = timezone.localdate()
    games = list(
        Session.objects
        .filter(division=team_season.division, season=team_season.season, date__gte=today)
        .order_by('date', 'start_time')[:5]
    )

    auto_print = request.GET.get('print', '1') != '0'

    return render(request, 'players/print_dugout_card.html', {
        'team_season': team_season,
        'head_coach': head_coach,
        'assistant_coaches': assistant_coaches,
        'roster': roster,
        'games': games,
        'auto_print': auto_print,
    })


# ---------------------------------------------------------------------------
# Family — SFLL-95 (Phase 4)
#
# A "family" is the set of PlayerSeasons in the active season that share an
# account_email (the SportsConnect payer). No Family model yet; identity is
# the email, URL-encoded with urlsafe-b64 so it round-trips cleanly in paths.
# Real models for Balance and VolunteerObligation land in later phases — the
# detail page surfaces structured empty shells today so the treasurer +
# division-coordinator workflows have a stable place to land once data exists.
# ---------------------------------------------------------------------------

FAMILY_COMMS_LIMIT = 20

# Roles that may access family-level data (contacts, comms, balance).
_FAMILY_ACCESS_ROLES = ('cto', 'ses_manager', 'vp_player_agents', 'president', 'player_agent', 'treasurer')


def encode_family_key(email):
    """Stable, URL-safe handle for a family (currently their account email)."""
    return urlsafe_base64_encode((email or '').strip().lower().encode())


def _decode_family_key(family_key):
    try:
        return urlsafe_base64_decode(family_key).decode()
    except (ValueError, UnicodeDecodeError):
        raise Http404("Unknown family")


def _user_has_role(user, *role_names, league=None):
    if user.is_superuser:
        return True
    qs = user.roles.filter(is_active=True, role__in=role_names)
    if league is not None:
        qs = qs.filter(league=league)
    return qs.exists()


def _treasurer_view_only(user, league=None):
    """True if this user can see balances but not edit anything else.

    Treasurers handle dues and outstanding balances; admin/finance edits are
    out-of-scope for the family detail page until a real Balance model lands.
    Scoped to `league` when provided so a treasurer on a different League
    does not get visibility into this family's balance.
    """
    if user.is_superuser:
        return False
    role_qs = user.roles.filter(is_active=True)
    if league is not None:
        role_qs = role_qs.filter(league=league)
    roles = set(role_qs.values_list('role', flat=True))
    admin_roles = {'cto', 'ses_manager', 'vp_player_agents', 'president', 'player_agent'}
    return 'treasurer' in roles and not (roles & admin_roles)


@login_required
def family_index(request):
    """List all families in the active season, ordered by account name.

    Built off PlayerSeason.account_email grouping rather than a dedicated
    Family table — that import path already exists from SportsConnect and we
    don't want to invent a new entity until it earns its keep.
    """
    if not _user_has_role(request.user, *_FAMILY_ACCESS_ROLES):
        raise PermissionDenied

    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        return render(request, 'players/family_index.html', {
            'families': [],
            'season': None,
        })

    rows = (
        PlayerSeason.objects
        .filter(season=active_season)
        .exclude(account_email='')
        .values('account_email', 'account_name')
        .annotate(player_count=Count('id'))
        .order_by('account_name', 'account_email')
    )

    # Same email may show under slightly different account_names across
    # registrations; pick the most common name per email.
    grouped = {}
    for row in rows:
        email = (row['account_email'] or '').lower()
        entry = grouped.setdefault(email, {
            'email': email,
            'names': Counter(),
            'player_count': 0,
        })
        entry['names'][row['account_name'] or '(no name)'] += row['player_count']
        entry['player_count'] += row['player_count']

    families = []
    for email, entry in grouped.items():
        name = entry['names'].most_common(1)[0][0]
        families.append({
            'email': email,
            'name': name,
            'player_count': entry['player_count'],
            'family_key': encode_family_key(email),
        })
    families.sort(key=lambda f: (f['name'].lower(), f['email']))

    return render(request, 'players/family_index.html', {
        'families': families,
        'season': active_season,
    })


@login_required
def family_detail(request, family_key):
    """Family detail — players, contacts, balance, volunteer obligations, comms.

    Sections that don't yet have backing models (Balance, VolunteerObligation)
    render as structured empty shells. The treasurer role flips the page into
    read-only mode — same surface, no edit affordances.
    """
    email = _decode_family_key(family_key).lower()
    if not email:
        raise Http404("Unknown family")

    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        raise Http404("No active season")

    if not _user_has_role(request.user, *_FAMILY_ACCESS_ROLES, league=active_season.league):
        raise PermissionDenied

    player_seasons = list(
        PlayerSeason.objects
        .filter(season=active_season, account_email__iexact=email)
        .select_related(
            'player', 'division', 'assigned_team__team', 'assigned_team__division',
        )
        .order_by('player__last_name', 'player__first_name')
    )
    if not player_seasons:
        raise Http404("No players in this family")

    # Account name: pick the most common spelling across siblings.
    name_counter = Counter(
        (ps.account_name or '').strip() for ps in player_seasons if ps.account_name
    )
    account_name = name_counter.most_common(1)[0][0] if name_counter else email

    # Contacts grid — derived from the SportsConnect payload (account_email +
    # additional_email). Emergency contact has no model field yet; surface a
    # placeholder so the slot is visible.
    additional_emails = [
        ps.additional_email for ps in player_seasons if ps.additional_email
    ]
    secondary_email = next(iter(dict.fromkeys(additional_emails)), '')
    contacts = [
        {
            'role': 'Primary parent',
            'role_badge': 'primary',
            'name': account_name,
            'email': email,
            'phone': '',
            'is_placeholder': False,
        },
        {
            'role': 'Secondary contact',
            'role_badge': 'secondary',
            'name': '',
            'email': secondary_email,
            'phone': '',
            'is_placeholder': not secondary_email,
        },
        {
            'role': 'Emergency contact',
            'role_badge': 'emergency',
            'name': '',
            'email': '',
            'phone': '',
            'is_placeholder': True,
        },
    ]

    # Division-level volunteer policy — division.name is enough context for
    # now; per-division pledged hours live in a config table that doesn't
    # exist yet. Surface what we know plus the empty shell.
    division_names = sorted({
        ps.division.name for ps in player_seasons if ps.division
    })

    # Comms history — last N outbound emails to any sibling in this family.
    # Pulled fresh from EmailLog so the family page becomes the audit surface
    # for "did we send them the SES reminder?"
    from communications.models import EmailLog  # local import to avoid cycle
    comms_rows = list(
        EmailLog.objects
        .filter(player_season__in=player_seasons)
        .select_related('player_season__player', 'template')
        .order_by('-sent_at')[:FAMILY_COMMS_LIMIT]
    )

    league = active_season.league
    treasurer_only = _treasurer_view_only(request.user, league=league)
    is_admin = _user_has_role(
        request.user,
        'cto', 'ses_manager', 'vp_player_agents', 'president', 'player_agent',
        league=league,
    )
    can_see_balance = treasurer_only or is_admin

    return render(request, 'players/family_detail.html', {
        'email': email,
        'family_key': family_key,
        'account_name': account_name,
        'player_seasons': player_seasons,
        'contacts': contacts,
        'division_names': division_names,
        'comms_rows': comms_rows,
        'season': active_season,
        'treasurer_only': treasurer_only,
        'can_see_balance': can_see_balance,
        'comms_limit': FAMILY_COMMS_LIMIT,
    })
