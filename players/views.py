from collections import Counter

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import Division, Player, PlayerSeason, Season, Team, TeamSeason


@login_required
def index(request):
    """Player roster — filterable by division and season."""
    active_season = Season.objects.filter(is_active=True).first()
    player_seasons = PlayerSeason.objects.select_related(
        'player', 'division', 'assigned_team__team',
    ).filter(season=active_season) if active_season else PlayerSeason.objects.none()

    return render(request, 'players/index.html', {
        'player_seasons': player_seasons,
        'season': active_season,
        'divisions': Division.objects.filter(is_active=True),
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


def encode_family_key(email):
    """Stable, URL-safe handle for a family (currently their account email)."""
    return urlsafe_base64_encode((email or '').strip().lower().encode())


def _decode_family_key(family_key):
    try:
        return urlsafe_base64_decode(family_key).decode()
    except (ValueError, UnicodeDecodeError):
        raise Http404("Unknown family")


def _user_has_role(user, *role_names):
    if user.is_superuser:
        return True
    return user.roles.filter(is_active=True, role__in=role_names).exists()


def _treasurer_view_only(user):
    """True if this user can see balances but not edit anything else.

    Treasurers handle dues and outstanding balances; admin/finance edits are
    out-of-scope for the family detail page until a real Balance model lands.
    """
    if user.is_superuser:
        return False
    roles = set(
        user.roles.filter(is_active=True).values_list('role', flat=True),
    )
    admin_roles = {'cto', 'ses_manager', 'vp_player_agents', 'president', 'player_agent'}
    return 'treasurer' in roles and not (roles & admin_roles)


@login_required
def family_index(request):
    """List all families in the active season, ordered by account name.

    Built off PlayerSeason.account_email grouping rather than a dedicated
    Family table — that import path already exists from SportsConnect and we
    don't want to invent a new entity until it earns its keep.
    """
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

    treasurer_only = _treasurer_view_only(request.user)
    is_admin = _user_has_role(
        request.user,
        'cto', 'ses_manager', 'vp_player_agents', 'president', 'player_agent',
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
