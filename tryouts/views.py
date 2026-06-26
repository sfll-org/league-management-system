from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import AuditLog
from evaluations.models import Evaluation
from players.models import Division, PlayerSeason, Season, Station

from .models import CheckIn, Session, SessionAssignment, WalkIn
from .utils import generate_checkin_qr

KIOSK_FEED_LIMIT = 20


def _can_manage_sessions(user):
    """Check if user has permission to create/edit/delete sessions."""
    if user.is_superuser:
        return True
    return user.roles.filter(
        is_active=True,
        role__in=[
            "cto",
            "ses_manager",
            "vp_player_agents",
            "president",
            "player_agent",
        ],
    ).exists()


def _get_active_season():
    """Return the current active season or None."""
    return Season.objects.filter(is_active=True).first()


@login_required
def session_list(request):
    """List SES sessions for the active season, with optional division filter."""
    active_season = _get_active_season()
    if not active_season:
        return render(
            request,
            "tryouts/session_list.html",
            {
                "upcoming_sessions": [],
                "past_sessions": [],
                "season": None,
                "divisions": [],
                "selected_division": None,
                "can_manage": _can_manage_sessions(request.user),
            },
        )

    sessions = Session.objects.select_related("division", "season").filter(
        season=active_season,
    )

    # Division filter
    division_id = request.GET.get("division")
    selected_division = None
    if division_id:
        try:
            selected_division = Division.objects.get(pk=division_id)
            sessions = sessions.filter(division=selected_division)
        except Division.DoesNotExist:
            pass

    divisions = Division.objects.filter(
        league=active_season.league,
        is_active=True,
    ).order_by("display_order")

    # Annotate with counts
    sessions = sessions.prefetch_related("assignments", "assignments__checkin")

    today = timezone.localdate()
    upcoming = [s for s in sessions if s.date >= today]
    past = [s for s in sessions if s.date < today]

    # Sort upcoming ascending (soonest first), past descending (most recent first)
    upcoming.sort(key=lambda s: (s.date, s.start_time))
    past.sort(key=lambda s: (s.date, s.start_time), reverse=True)

    return render(
        request,
        "tryouts/session_list.html",
        {
            "upcoming_sessions": upcoming,
            "past_sessions": past,
            "season": active_season,
            "divisions": divisions,
            "selected_division": selected_division,
            "can_manage": _can_manage_sessions(request.user),
        },
    )


@login_required
def session_detail(request, pk):
    """SES Session screen — stat row, per-station progress, check-in roster, no-show queue."""
    session = get_object_or_404(
        Session.objects.select_related("division", "season", "makeup_for"),
        pk=pk,
    )
    q = (request.GET.get("q") or "").strip()
    context = _build_ses_session_context(session, request.user, q=q)
    return render(request, "tryouts/session_detail.html", context)


def _ses_assignments_qs(session):
    """All assignments for a session with related player/division and check-in prefetched."""
    return (
        SessionAssignment.objects.select_related(
            "player_season__player", "player_season__division"
        )
        .prefetch_related("checkin")
        .filter(session=session)
        .order_by(
            "player_season__player__last_name", "player_season__player__first_name"
        )
    )


def _annotate_assignment(a):
    """Return a flat dict view of an assignment for templates."""
    try:
        checkin = a.checkin
        checked_in = True
    except CheckIn.DoesNotExist:
        checkin = None
        checked_in = False
    return {
        "assignment": a,
        "player_season": a.player_season,
        "player": a.player_season.player,
        "division": a.player_season.division,
        "account_name": a.player_season.account_name,
        "checked_in": checked_in,
        "checkin": checkin,
    }


def _on_station_player_ids(session):
    """PlayerSeason ids that have at least one Evaluation for this session."""
    return set(
        Evaluation.objects.filter(session=session)
        .values_list("player_season_id", flat=True)
        .distinct()
    )


def _station_progress(session, checked_in_count):
    """Per-station small-multiple progress: distinct players evaluated / total checked in."""
    stations = list(
        Station.objects.filter(league=session.division.league, is_active=True).order_by(
            "display_order"
        )
    )
    eval_counts = {
        row["station_id"]: row["n"]
        for row in (
            Evaluation.objects.filter(session=session)
            .values("station_id")
            .annotate(n=Count("player_season_id", distinct=True))
        )
    }
    expected = checked_in_count or 0
    progress = []
    for station in stations:
        evaluated = eval_counts.get(station.pk, 0)
        if expected <= 0:
            pct = 0
        else:
            pct = min(100, int(round(evaluated * 100 / expected)))
        if expected == 0 or evaluated == 0:
            state = "idle"
        elif evaluated >= expected:
            state = "done"
        else:
            state = "in_progress"
        progress.append(
            {
                "station": station,
                "evaluated": evaluated,
                "expected": expected,
                "pct": pct,
                "state": state,
            }
        )
    return progress


def _next_makeup_target(session):
    """Pick the next available session in the same division for one-click reschedule.

    Prefers an upcoming makeup session for this division; falls back to the next
    regular session if no makeup is scheduled. Returns ``None`` if none qualify.
    """
    today = timezone.localdate()
    upcoming = (
        Session.objects.filter(
            season=session.season,
            division=session.division,
            date__gte=today,
        )
        .exclude(pk=session.pk)
        .order_by("date", "start_time")
    )
    makeup = upcoming.filter(is_makeup=True).first()
    if makeup:
        return makeup
    return upcoming.first()


def _no_show_queue(session, assignment_data):
    """Assignments that registered but didn't check in (the no-show queue)."""
    target = _next_makeup_target(session)
    queue = []
    for row in assignment_data:
        if row["checked_in"]:
            continue
        queue.append(
            {
                **row,
                "reschedule_target": target,
                "is_flagged": row["player_season"].status == "needs_makeup",
            }
        )
    return queue


def _filter_roster(assignment_data, q):
    if not q:
        return assignment_data
    needle = q.lower()
    out = []
    for row in assignment_data:
        p = row["player"]
        if needle in p.first_name.lower() or needle in p.last_name.lower():
            out.append(row)
            continue
        full = f"{p.first_name} {p.last_name}".lower()
        if needle in full:
            out.append(row)
    return out


def _build_ses_session_context(session, user, q=""):
    """Assemble the full context dict for the SES Session screen."""
    assignments = _ses_assignments_qs(session)
    full_roster = [_annotate_assignment(a) for a in assignments]
    checked_in_count = sum(1 for r in full_roster if r["checked_in"])
    on_station_ids = _on_station_player_ids(session)
    on_station_count = sum(
        1
        for r in full_roster
        if r["checked_in"] and r["player_season"].pk in on_station_ids
    )
    no_show_count = len(full_roster) - checked_in_count

    stats = {
        "registered": len(full_roster),
        "checked_in": checked_in_count,
        "no_show": no_show_count,
        "on_station": on_station_count,
    }

    return {
        "session": session,
        "stats": stats,
        "station_progress": _station_progress(session, checked_in_count),
        "roster": _filter_roster(full_roster, q),
        "roster_total": len(full_roster),
        "no_show_queue": _no_show_queue(session, full_roster),
        "q": q,
        "can_manage": _can_manage_sessions(user),
        "can_checkin": _can_checkin(user),
        "can_reassign": _can_reassign(user),
    }


@login_required
def session_create(request):
    """Create a new SES session."""
    if not _can_manage_sessions(request.user):
        return HttpResponseForbidden("You do not have permission to create sessions.")

    active_season = _get_active_season()
    if not active_season:
        messages.error(request, "No active season. Cannot create a session.")
        return redirect("tryouts:session_list")

    divisions = Division.objects.filter(
        league=active_season.league,
        is_active=True,
    ).order_by("display_order")

    # Existing sessions for makeup_for dropdown
    existing_sessions = Session.objects.filter(season=active_season).order_by("date")

    if request.method == "POST":
        return _save_session(request, active_season, divisions, existing_sessions)

    return render(
        request,
        "tryouts/session_form.html",
        {
            "is_edit": False,
            "season": active_season,
            "divisions": divisions,
            "existing_sessions": existing_sessions,
        },
    )


@login_required
def session_edit(request, pk):
    """Edit an existing SES session."""
    if not _can_manage_sessions(request.user):
        return HttpResponseForbidden("You do not have permission to edit sessions.")

    session = get_object_or_404(Session, pk=pk)
    active_season = session.season

    divisions = Division.objects.filter(
        league=active_season.league,
        is_active=True,
    ).order_by("display_order")

    existing_sessions = (
        Session.objects.filter(
            season=active_season,
        )
        .exclude(pk=pk)
        .order_by("date")
    )

    if request.method == "POST":
        return _save_session(
            request,
            active_season,
            divisions,
            existing_sessions,
            session=session,
        )

    return render(
        request,
        "tryouts/session_form.html",
        {
            "is_edit": True,
            "session": session,
            "season": active_season,
            "divisions": divisions,
            "existing_sessions": existing_sessions,
        },
    )


def _save_session(request, season, divisions, existing_sessions, session=None):
    """Shared save logic for create/edit."""
    name = request.POST.get("name", "").strip()
    date_str = request.POST.get("date", "").strip()
    start_time = request.POST.get("start_time", "").strip()
    end_time = request.POST.get("end_time", "").strip() or None
    location = request.POST.get("location", "").strip()
    division_id = request.POST.get("division", "")
    is_makeup = request.POST.get("is_makeup") == "on"
    makeup_for_id = request.POST.get("makeup_for", "") or None

    # Validation
    errors = []
    if not name:
        errors.append("Name is required.")
    if not date_str:
        errors.append("Date is required.")
    if not start_time:
        errors.append("Start time is required.")
    if not division_id:
        errors.append("Division is required.")

    if errors:
        for e in errors:
            messages.error(request, e)
        return render(
            request,
            "tryouts/session_form.html",
            {
                "is_edit": session is not None,
                "session": session,
                "season": season,
                "divisions": divisions,
                "existing_sessions": existing_sessions,
                "form_data": request.POST,
            },
        )

    # Resolve FKs
    try:
        division = Division.objects.get(pk=division_id)
    except Division.DoesNotExist:
        messages.error(request, "Invalid division.")
        return redirect("tryouts:session_list")

    makeup_for = None
    if is_makeup and makeup_for_id:
        try:
            makeup_for = Session.objects.get(pk=makeup_for_id)
        except Session.DoesNotExist:
            pass

    if session is None:
        session = Session()
        session.season = season

    session.name = name
    session.date = date_str
    session.start_time = start_time
    session.end_time = end_time
    session.location = location
    session.division = division
    session.is_makeup = is_makeup
    session.makeup_for = makeup_for
    session.save()

    action = "updated" if session.pk else "created"
    messages.success(request, f'Session "{session.name}" saved successfully.')
    return redirect("tryouts:session_detail", pk=session.pk)


@login_required
def session_delete(request, pk):
    """Delete an SES session with confirmation."""
    if not _can_manage_sessions(request.user):
        return HttpResponseForbidden("You do not have permission to delete sessions.")

    session = get_object_or_404(Session, pk=pk)

    if request.method == "POST":
        name = session.name
        session.delete()
        messages.success(request, f'Session "{name}" deleted.')
        return redirect("tryouts:session_list")

    return render(
        request,
        "tryouts/session_delete.html",
        {
            "session": session,
        },
    )


@login_required
def session_assign_players(request, pk):
    """HTMX view: show/toggle player assignments for a session."""
    session = get_object_or_404(
        Session.objects.select_related("division", "season"),
        pk=pk,
    )
    can_manage = _can_manage_sessions(request.user)

    if request.method == "POST" and can_manage:
        player_season_id = request.POST.get("player_season_id")
        if player_season_id:
            try:
                ps = PlayerSeason.objects.get(pk=player_season_id)
                existing = SessionAssignment.objects.filter(
                    session=session,
                    player_season=ps,
                )
                if existing.exists():
                    existing.delete()
                else:
                    SessionAssignment.objects.create(
                        session=session,
                        player_season=ps,
                        assigned_by=request.user,
                    )
            except PlayerSeason.DoesNotExist:
                pass

    # Build player list for this division
    player_seasons = (
        PlayerSeason.objects.select_related("player")
        .filter(
            season=session.season,
            division=session.division,
        )
        .order_by("player__last_name", "player__first_name")
    )

    assigned_ids = set(
        SessionAssignment.objects.filter(session=session).values_list(
            "player_season_id",
            flat=True,
        )
    )

    player_data = []
    for ps in player_seasons:
        player_data.append(
            {
                "player_season": ps,
                "player": ps.player,
                "is_assigned": ps.pk in assigned_ids,
            }
        )

    return render(
        request,
        "tryouts/partials/player_assignments.html",
        {
            "session": session,
            "players": player_data,
            "assigned_count": len(assigned_ids),
            "total_count": len(player_data),
            "can_manage": can_manage,
        },
    )


# ---------------------------------------------------------------------------
# Check-in views
# ---------------------------------------------------------------------------


def _can_checkin(user):
    """Front desk, player agents, ses managers, cto can check in players."""
    if user.is_superuser:
        return True
    return user.roles.filter(
        is_active=True,
        role__in=[
            "cto",
            "ses_manager",
            "vp_player_agents",
            "president",
            "player_agent",
            "front_desk",
        ],
    ).exists()


def _build_assignment_data(assignments):
    """Build enriched assignment list with check-in status."""
    data = []
    checked_in_count = 0
    for a in assignments:
        try:
            checkin = a.checkin
            has_checkin = True
        except CheckIn.DoesNotExist:
            checkin = None
            has_checkin = False
        if has_checkin:
            checked_in_count += 1
        data.append(
            {
                "assignment": a,
                "player_season": a.player_season,
                "player": a.player_season.player,
                "division": a.player_season.division,
                "account_name": a.player_season.account_name,
                "checked_in": has_checkin,
                "checkin": checkin,
            }
        )
    return data, checked_in_count


@login_required
def session_checkin(request, pk):
    """iPad-optimized check-in dashboard for an SES session."""
    if not _can_checkin(request.user):
        return HttpResponseForbidden("You do not have permission to check in players.")

    session = get_object_or_404(
        Session.objects.select_related("division", "season"),
        pk=pk,
    )

    assignments = (
        SessionAssignment.objects.select_related(
            "player_season__player",
            "player_season__division",
        )
        .filter(session=session)
        .order_by("player_season__player__last_name")
    )

    # Prefetch check-ins
    assignments = assignments.prefetch_related("checkin")

    assignment_data, checked_in_count = _build_assignment_data(assignments)

    # Get today's sessions for session switcher
    today = timezone.localdate()
    todays_sessions = (
        Session.objects.filter(
            season=session.season,
            date=today,
        )
        .select_related("division")
        .order_by("start_time")
    )

    return render(
        request,
        "tryouts/checkin.html",
        {
            "session": session,
            "assignments": assignment_data,
            "assignment_count": len(assignment_data),
            "checked_in_count": checked_in_count,
            "todays_sessions": todays_sessions,
        },
    )


def checkin_by_token(request, token):
    """Public check-in via QR code — no authentication required."""
    player_season = get_object_or_404(
        PlayerSeason.objects.select_related("player", "season"), checkin_token=token
    )

    today = timezone.localdate()
    # Find today's session assignment for this player
    assignment = (
        SessionAssignment.objects.select_related(
            "session",
            "session__division",
        )
        .filter(
            player_season=player_season,
            session__date=today,
        )
        .first()
    )

    if not assignment:
        return render(
            request,
            "tryouts/checkin_confirm.html",
            {
                "player": player_season.player,
                "error": "No SES session found for today. Please check with the front desk.",
            },
        )

    # Check if already checked in
    try:
        existing = assignment.checkin
        return render(
            request,
            "tryouts/checkin_confirm.html",
            {
                "player": player_season.player,
                "session": assignment.session,
                "checkin": existing,
                "already_checked_in": True,
            },
        )
    except CheckIn.DoesNotExist:
        pass

    # Create check-in (no user — public QR scan)
    checkin = CheckIn.objects.create(
        session_assignment=assignment,
        checked_in_by=None,
        notes="QR code check-in",
    )

    return render(
        request,
        "tryouts/checkin_confirm.html",
        {
            "player": player_season.player,
            "session": assignment.session,
            "checkin": checkin,
            "already_checked_in": False,
        },
    )


@login_required
def checkin_search(request, pk):
    """HTMX search: filter players by name within a session."""
    if not _can_checkin(request.user):
        return HttpResponseForbidden()

    session = get_object_or_404(Session, pk=pk)
    q = request.GET.get("q", "").strip()

    assignments = (
        SessionAssignment.objects.select_related(
            "player_season__player",
            "player_season__division",
        )
        .filter(session=session)
        .prefetch_related("checkin")
    )

    if q:
        assignments = assignments.filter(
            Q(player_season__player__first_name__icontains=q)
            | Q(player_season__player__last_name__icontains=q)
        )

    assignments = assignments.order_by("player_season__player__last_name")

    assignment_data, checked_in_count = _build_assignment_data(assignments)

    return render(
        request,
        "tryouts/partials/checkin_player_list.html",
        {
            "session": session,
            "assignments": assignment_data,
            "assignment_count": len(assignment_data),
            "checked_in_count": checked_in_count,
        },
    )


@login_required
@require_POST
def checkin_player(request, pk, assignment_id):
    """HTMX: check in a single player and return updated row."""
    if not _can_checkin(request.user):
        return HttpResponseForbidden()

    assignment = get_object_or_404(
        SessionAssignment.objects.select_related(
            "player_season__player",
            "player_season__division",
            "session",
        ),
        pk=assignment_id,
        session_id=pk,
    )

    # Idempotent — don't error if already checked in
    checkin, created = CheckIn.objects.get_or_create(
        session_assignment=assignment,
        defaults={
            "checked_in_by": request.user,
        },
    )

    # Get updated stats for OOB swap
    session = assignment.session
    total_assigned = session.assignments.count()
    total_checked_in = CheckIn.objects.filter(
        session_assignment__session=session
    ).count()

    return render(
        request,
        "tryouts/partials/checkin_player_row.html",
        {
            "a": {
                "assignment": assignment,
                "player_season": assignment.player_season,
                "player": assignment.player_season.player,
                "division": assignment.player_season.division,
                "account_name": assignment.player_season.account_name,
                "checked_in": True,
                "checkin": checkin,
            },
            "session": session,
            "total_assigned": total_assigned,
            "total_checked_in": total_checked_in,
            "include_stats_oob": True,
        },
    )


# ---------------------------------------------------------------------------
# Session reassignment
# ---------------------------------------------------------------------------


def _can_reassign(user):
    """Check if user can reassign players between sessions."""
    if user.is_superuser:
        return True
    return user.roles.filter(
        is_active=True,
        role__in=["cto", "ses_manager", "player_agent", "front_desk"],
    ).exists()


@login_required
def reassign_player(request, pk, assignment_id):
    """Reassign a player from one session to another in the same division."""
    if not _can_reassign(request.user):
        return HttpResponseForbidden("You do not have permission to reassign players.")

    assignment = get_object_or_404(
        SessionAssignment.objects.select_related(
            "session__division",
            "session__season",
            "player_season__player",
        ),
        pk=assignment_id,
        session_id=pk,
    )
    source_session = assignment.session

    # Available target sessions: same division, same season, not the current one
    target_sessions = (
        Session.objects.filter(
            season=source_session.season,
            division=source_session.division,
        )
        .exclude(pk=source_session.pk)
        .order_by("date", "start_time")
    )

    if request.method == "POST":
        target_session_id = request.POST.get("target_session")
        reason = request.POST.get("reason", "").strip()

        if not target_session_id:
            messages.error(request, "Please select a target session.")
            return render(
                request,
                "tryouts/reassign.html",
                {
                    "assignment": assignment,
                    "source_session": source_session,
                    "player": assignment.player_season.player,
                    "player_season": assignment.player_season,
                    "target_sessions": target_sessions,
                    "form_data": request.POST,
                },
            )

        target_session = get_object_or_404(
            Session,
            pk=target_session_id,
            season=source_session.season,
            division=source_session.division,
        )

        # Check the player isn't already assigned to the target session
        if SessionAssignment.objects.filter(
            session=target_session,
            player_season=assignment.player_season,
        ).exists():
            messages.error(
                request,
                f"Player is already assigned to {target_session.name}.",
            )
            return render(
                request,
                "tryouts/reassign.html",
                {
                    "assignment": assignment,
                    "source_session": source_session,
                    "player": assignment.player_season.player,
                    "player_season": assignment.player_season,
                    "target_sessions": target_sessions,
                    "form_data": request.POST,
                },
            )

        # Create new assignment in target session
        SessionAssignment.objects.create(
            session=target_session,
            player_season=assignment.player_season,
            assigned_by=request.user,
        )

        # Record audit log
        AuditLog.objects.create(
            user=request.user,
            action="player.reassign",
            entity_type="SessionAssignment",
            entity_id=assignment.pk,
            details={
                "from_session_id": source_session.pk,
                "from_session_name": source_session.name,
                "to_session_id": target_session.pk,
                "to_session_name": target_session.name,
                "player_season_id": assignment.player_season.pk,
                "player_name": str(assignment.player_season.player),
                "reason": reason,
            },
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        # Capture player name before deleting the assignment; accessing it after
        # delete is fragile (relies on in-memory cache; any refetch raises DoesNotExist).
        player_name = assignment.player_season.player.full_name

        # Delete old assignment
        assignment.delete()

        messages.success(
            request,
            f"{player_name} reassigned from {source_session.name} to {target_session.name}.",
        )

        # If HTMX request, return to the check-in dashboard
        if request.headers.get("HX-Request"):
            return redirect("tryouts:session_checkin", pk=source_session.pk)
        return redirect("tryouts:session_detail", pk=source_session.pk)

    return render(
        request,
        "tryouts/reassign.html",
        {
            "assignment": assignment,
            "source_session": source_session,
            "player": assignment.player_season.player,
            "player_season": assignment.player_season,
            "target_sessions": target_sessions,
        },
    )


# ---------------------------------------------------------------------------
# No-show flagging
# ---------------------------------------------------------------------------


def _can_flag_noshows(user):
    """Check if user can flag no-shows."""
    if user.is_superuser:
        return True
    return user.roles.filter(
        is_active=True,
        role__in=["cto", "ses_manager", "player_agent"],
    ).exists()


@login_required
def flag_noshows(request, pk):
    """Show and flag players who were assigned but did not check in."""
    if not _can_flag_noshows(request.user):
        return HttpResponseForbidden("You do not have permission to flag no-shows.")

    session = get_object_or_404(
        Session.objects.select_related("division", "season"),
        pk=pk,
    )

    # All assignments for this session
    assignments = (
        SessionAssignment.objects.select_related(
            "player_season__player",
            "player_season__division",
        )
        .filter(session=session)
        .order_by("player_season__player__last_name")
    )

    # Find no-shows: assignments with no CheckIn record
    noshow_assignments = []
    total_count = 0
    for a in assignments:
        total_count += 1
        try:
            _ = a.checkin
        except CheckIn.DoesNotExist:
            noshow_assignments.append(
                {
                    "assignment": a,
                    "player_season": a.player_season,
                    "player": a.player_season.player,
                }
            )

    if request.method == "POST":
        # Flag selected players for makeup
        flagged_ids = request.POST.getlist("flag_player_season")
        flagged_count = 0
        for ps_id in flagged_ids:
            try:
                ps = PlayerSeason.objects.get(pk=ps_id)
                # Mark the player season status so they need a makeup
                if ps.status != "needs_makeup":
                    ps.status = "needs_makeup"
                    ps.save(update_fields=["status"])
                    flagged_count += 1

                    AuditLog.objects.create(
                        user=request.user,
                        action="player.noshow_flagged",
                        entity_type="PlayerSeason",
                        entity_id=ps.pk,
                        details={
                            "session_id": session.pk,
                            "session_name": session.name,
                            "player_name": str(ps.player),
                        },
                        ip_address=request.META.get("REMOTE_ADDR"),
                    )
            except PlayerSeason.DoesNotExist:
                continue

        if flagged_count:
            messages.success(
                request,
                f"{flagged_count} player(s) flagged for makeup session.",
            )
        else:
            messages.info(request, "No players were flagged.")

        return redirect("tryouts:flag_noshows", pk=session.pk)

    return render(
        request,
        "tryouts/noshows.html",
        {
            "session": session,
            "noshow_assignments": noshow_assignments,
            "noshow_count": len(noshow_assignments),
            "total_count": total_count,
            "can_manage": _can_manage_sessions(request.user),
        },
    )


# ---------------------------------------------------------------------------
# QR code views
# ---------------------------------------------------------------------------


def _kiosk_assignments_for_today(season):
    """All SessionAssignments for today across the active season's sessions.

    Returns the queryset plus the date so callers don't have to recompute it.
    The view selects across all divisions running at Big Rec on the same day,
    which is the front-desk reality the kiosk is built for.
    """
    today = timezone.localdate()
    qs = (
        SessionAssignment.objects.select_related(
            'session', 'session__division',
            'player_season__player', 'player_season__division',
        )
        .filter(session__season=season, session__date=today)
        .prefetch_related('checkin')
        .order_by('player_season__player__last_name', 'player_season__player__first_name')
    )
    return qs, today


def _kiosk_build_tiles(assignments, session_filter_id=None, search=''):
    """Materialize the tile dataset the kiosk grid renders."""
    tiles = []
    sessions_seen = {}
    total = 0
    checked_in = 0
    search_lower = (search or '').strip().lower()

    for a in assignments:
        sess = a.session
        sessions_seen.setdefault(sess.pk, {
            'session': sess,
            'count': 0,
            'checked_in': 0,
        })
        sessions_seen[sess.pk]['count'] += 1
        total += 1

        try:
            checkin = a.checkin
            has_checkin = True
        except CheckIn.DoesNotExist:
            checkin = None
            has_checkin = False

        if has_checkin:
            sessions_seen[sess.pk]['checked_in'] += 1
            checked_in += 1

        if session_filter_id and sess.pk != session_filter_id:
            continue
        if search_lower:
            player = a.player_season.player
            haystack = f"{player.first_name} {player.last_name}".lower()
            if search_lower not in haystack:
                continue

        ps = a.player_season
        tiles.append({
            'assignment': a,
            'player': ps.player,
            'player_season': ps,
            'session': sess,
            'division': sess.division,
            'checked_in': has_checkin,
            'checkin': checkin,
        })

    session_filters = sorted(
        sessions_seen.values(),
        key=lambda s: (s['session'].start_time, s['session'].name),
    )
    return tiles, session_filters, total, checked_in


def _kiosk_recent_feed(season):
    """Most-recent check-ins today, newest first."""
    today = timezone.localdate()
    checkins = list(
        CheckIn.objects.select_related(
            'session_assignment__player_season__player',
            'session_assignment__session__division',
        )
        .filter(session_assignment__session__season=season,
                session_assignment__session__date=today)
        .order_by('-checked_in_at')[:KIOSK_FEED_LIMIT]
    )
    return checkins


def _kiosk_today_walk_ins(season):
    """Walk-ins logged today for this season (regardless of session linkage)."""
    today = timezone.localdate()
    return list(
        WalkIn.objects.select_related('division', 'session')
        .filter(logged_at__date=today, season=season)
        .order_by('-logged_at')[:KIOSK_FEED_LIMIT]
    )


@login_required
def kiosk(request):
    """iPad-landscape front-desk kiosk for SES check-in at Big Rec.

    Pulls every player assigned to a session today (across divisions) into a
    single 6-col tile grid. Volunteers tap a tile, confirm in a modal, and the
    live feed on the right rail surfaces the most recent check-ins so the desk
    can immediately see the action they just took.
    """
    if not _can_checkin(request.user):
        return HttpResponseForbidden("You do not have permission to check in players.")

    active_season = _get_active_season()
    if not active_season:
        return render(request, 'tryouts/kiosk.html', {
            'season': None,
            'today': timezone.localdate(),
            'tiles': [],
            'session_filters': [],
            'today_sessions': [],
            'total_count': 0,
            'checked_in_count': 0,
            'selected_session_id': None,
            'feed': [],
            'walk_ins': [],
        })

    try:
        session_filter_id = int(request.GET.get('session') or 0) or None
    except ValueError:
        session_filter_id = None

    assignments, today = _kiosk_assignments_for_today(active_season)
    tiles, session_filters, total, checked_in = _kiosk_build_tiles(
        assignments, session_filter_id=session_filter_id,
    )
    feed = _kiosk_recent_feed(active_season)
    walk_ins = _kiosk_today_walk_ins(active_season)

    # today_sessions feeds the walk-in form division/session pickers
    today_sessions = [sf['session'] for sf in session_filters]

    return render(request, 'tryouts/kiosk.html', {
        'season': active_season,
        'today': today,
        'tiles': tiles,
        'session_filters': session_filters,
        'today_sessions': today_sessions,
        'total_count': total,
        'checked_in_count': checked_in,
        'selected_session_id': session_filter_id,
        'feed': feed,
        'walk_ins': walk_ins,
    })


@login_required
def kiosk_search(request):
    """HTMX endpoint: re-render the kiosk grid for a name search + session filter."""
    if not _can_checkin(request.user):
        return HttpResponseForbidden()

    active_season = _get_active_season()
    if not active_season:
        return render(request, 'tryouts/partials/kiosk_grid.html', {'tiles': []})

    try:
        session_filter_id = int(request.GET.get('session') or 0) or None
    except ValueError:
        session_filter_id = None
    search = request.GET.get('q', '')

    assignments, _ = _kiosk_assignments_for_today(active_season)
    tiles, _filters, _total, _checked = _kiosk_build_tiles(
        assignments, session_filter_id=session_filter_id, search=search,
    )

    return render(request, 'tryouts/partials/kiosk_grid.html', {
        'tiles': tiles,
        'selected_session_id': session_filter_id,
    })


@login_required
@require_POST
def kiosk_checkin(request, assignment_id):
    """HTMX: record a check-in from the kiosk; returns updated tile + OOB feed/stat."""
    if not _can_checkin(request.user):
        return HttpResponseForbidden()

    active_season = _get_active_season()
    if not active_season:
        return HttpResponseForbidden()

    assignment = get_object_or_404(
        SessionAssignment.objects.select_related(
            'session__division', 'player_season__player',
        ),
        pk=assignment_id,
        session__season=active_season,
        session__date=timezone.localdate(),
    )

    checkin, _created = CheckIn.objects.get_or_create(
        session_assignment=assignment,
        defaults={'checked_in_by': request.user, 'notes': 'kiosk'},
    )

    assignments, _ = _kiosk_assignments_for_today(active_season)
    _tiles, _filters, total, checked_in = _kiosk_build_tiles(assignments)
    feed = _kiosk_recent_feed(active_season)

    walk_ins = _kiosk_today_walk_ins(active_season)

    tile = {
        'assignment': assignment,
        'player': assignment.player_season.player,
        'player_season': assignment.player_season,
        'session': assignment.session,
        'division': assignment.session.division,
        'checked_in': True,
        'checkin': checkin,
    }

    return render(request, 'tryouts/partials/kiosk_tile_after_checkin.html', {
        'tile': tile,
        'feed': feed,
        'walk_ins': walk_ins,
        'total_count': total,
        'checked_in_count': checked_in,
    })


@login_required
@require_POST
def kiosk_walkin(request):
    """Log a walk-in player who has no PlayerSeason record."""
    if not _can_checkin(request.user):
        return HttpResponseForbidden()

    active_season = _get_active_season()
    if not active_season:
        return HttpResponseForbidden()

    first_name = (request.POST.get('first_name') or '').strip()
    last_name = (request.POST.get('last_name') or '').strip()
    if not first_name or not last_name:
        return HttpResponse('Name is required.', status=400)

    division_id = request.POST.get('division') or None
    session_id = request.POST.get('session') or None

    division = None
    if division_id:
        from players.models import Division as Div
        division = Div.objects.filter(pk=division_id).first()

    session = None
    if session_id:
        session = Session.objects.filter(
            pk=session_id, season=active_season,
        ).select_related('division').first()
        if session and division is None:
            division = session.division

    WalkIn.objects.create(
        first_name=first_name,
        last_name=last_name,
        season=active_season,
        division=division,
        session=session,
        logged_by=request.user,
        notes=request.POST.get('notes', '').strip(),
    )

    feed = _kiosk_recent_feed(active_season)
    walk_ins = _kiosk_today_walk_ins(active_season)
    return render(request, 'tryouts/partials/kiosk_walkin_response.html', {
        'feed': feed,
        'walk_ins': walk_ins,
        'walk_in_name': f"{last_name}, {first_name}",
    })


@login_required

def player_qr_code(request, player_season_id):
    """Generate and return a QR code PNG for a player's check-in token."""
    ps = get_object_or_404(PlayerSeason, pk=player_season_id)
    png_data = generate_checkin_qr(ps.checkin_token)
    return HttpResponse(png_data, content_type="image/png")


@login_required
def session_qr_codes(request, pk):
    """Printable page with QR codes for all assigned players in a session."""
    session = get_object_or_404(
        Session.objects.select_related("division", "season"),
        pk=pk,
    )
    assignments = (
        SessionAssignment.objects.select_related(
            "player_season__player",
        )
        .filter(session=session)
        .order_by("player_season__player__last_name")
    )

    player_data = []
    for a in assignments:
        player_data.append(
            {
                "player": a.player_season.player,
                "player_season": a.player_season,
            }
        )

    return render(
        request,
        "tryouts/qr_codes.html",
        {
            "session": session,
            "players": player_data,
        },
    )


# ---------------------------------------------------------------------------
# SES Session screen — HTMX endpoints
# ---------------------------------------------------------------------------


@login_required
def ses_roster_search(request, pk):
    """HTMX: filter the SES Session screen's check-in roster by name."""
    session = get_object_or_404(
        Session.objects.select_related("division", "season"),
        pk=pk,
    )
    q = (request.GET.get("q") or "").strip()
    ctx = _build_ses_session_context(session, request.user, q=q)
    return render(request, "tryouts/partials/ses_roster.html", ctx)


@login_required
@require_POST
def ses_quick_checkin(request, pk, assignment_id):
    """HTMX: quick check-in from the SES Session screen.

    Returns the updated roster row and OOB-swaps the stat row + no-show queue
    so all three regions stay in sync after a single click.
    """
    if not _can_checkin(request.user):
        return HttpResponseForbidden()

    session = get_object_or_404(
        Session.objects.select_related("division", "season"),
        pk=pk,
    )
    assignment = get_object_or_404(
        SessionAssignment.objects.select_related(
            "player_season__player",
            "player_season__division",
        ),
        pk=assignment_id,
        session=session,
    )

    CheckIn.objects.get_or_create(
        session_assignment=assignment,
        defaults={"checked_in_by": request.user},
    )

    # Reload the assignment so the freshly-created CheckIn is on the prefetch.
    assignment = (
        SessionAssignment.objects.select_related(
            "player_season__player", "player_season__division"
        )
        .prefetch_related("checkin")
        .get(pk=assignment.pk)
    )
    ctx = _build_ses_session_context(
        session, request.user, q=request.GET.get("q") or ""
    )
    ctx["row"] = _annotate_assignment(assignment)
    return render(request, "tryouts/partials/ses_row_with_oob.html", ctx)


@login_required
@require_POST
def ses_quick_reschedule(request, pk, assignment_id):
    """HTMX: one-click reschedule a no-show to the next available session.

    Picks an upcoming makeup session in the same division if one exists, else
    the next regular session. Records an audit log entry, then re-renders the
    no-show queue (and OOB-swaps the stat row) so the screen reflects the move.
    """
    if not _can_reassign(request.user):
        return HttpResponseForbidden()

    session = get_object_or_404(
        Session.objects.select_related("division", "season"),
        pk=pk,
    )
    assignment = get_object_or_404(
        SessionAssignment.objects.select_related(
            "player_season__player",
            "session__division",
        ),
        pk=assignment_id,
        session=session,
    )

    target = _next_makeup_target(session)
    if target is None:
        # Return 200 so HTMX swaps the error message into #ses-noshow.
        # 4xx responses are not swapped by HTMX by default.
        return HttpResponse(
            '<div class="empty">No upcoming session available for one-click reschedule. '
            "Create a makeup session first.</div>",
        )

    # If the player is somehow already assigned to the target (defensive — UI
    # only surfaces a single CTA per row), no-op gracefully.
    already_there = SessionAssignment.objects.filter(
        session=target,
        player_season=assignment.player_season,
    ).exists()

    if not already_there:
        SessionAssignment.objects.create(
            session=target,
            player_season=assignment.player_season,
            assigned_by=request.user,
        )

    # Flag the PlayerSeason so downstream reports know they needed a makeup.
    ps = assignment.player_season
    if ps.status != "needs_makeup":
        ps.status = "needs_makeup"
        ps.save(update_fields=["status"])

    AuditLog.objects.create(
        user=request.user,
        action="player.quick_reschedule",
        entity_type="SessionAssignment",
        entity_id=assignment.pk,
        details={
            "from_session_id": session.pk,
            "from_session_name": session.name,
            "to_session_id": target.pk,
            "to_session_name": target.name,
            "player_season_id": ps.pk,
            "player_name": str(ps.player),
            "already_assigned_to_target": already_there,
        },
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Remove the original no-show assignment so the queue clears.
    assignment.delete()

    ctx = _build_ses_session_context(
        session, request.user, q=request.GET.get("q") or ""
    )
    ctx["reschedule_target"] = target
    return render(request, "tryouts/partials/ses_noshow_with_oob.html", ctx)
