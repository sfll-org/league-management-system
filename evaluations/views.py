import json
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max, Min
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import CoachSeason, UserRole
from players.models import Division, PlayerSeason, Season, Station
from tryouts.models import CheckIn, Session

from .models import Evaluation, ObjectiveMetric

# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------


def _get_coach_season(user, session):
    """Get the CoachSeason for this user in the session's season."""
    try:
        return CoachSeason.objects.get(
            coach__user=user,
            season=session.season,
        )
    except CoachSeason.DoesNotExist:
        return None
    except CoachSeason.MultipleObjectsReturned:
        return CoachSeason.objects.filter(
            coach__user=user,
            season=session.season,
        ).first()


def _is_eval_authorized(user):
    """Return True if user is a coach, CTO, SES manager, staff, or superuser."""
    if user.is_superuser or user.is_staff:
        return True
    return UserRole.objects.filter(
        user=user,
        is_active=True,
        role__in=["cto", "ses_manager", "head_coach", "assistant_coach"],
    ).exists()


def _get_coach_season_for_season(user, season):
    """Get the CoachSeason for this user in the given season (no session required)."""
    try:
        return CoachSeason.objects.get(coach__user=user, season=season)
    except CoachSeason.DoesNotExist:
        return None
    except CoachSeason.MultipleObjectsReturned:
        return CoachSeason.objects.filter(coach__user=user, season=season).first()


def _can_view_aggregated(user, division=None):
    """Can this user see aggregated eval reports?"""
    if user.is_superuser:
        return True
    roles = user.roles.filter(is_active=True)
    # Global roles can see everything
    if roles.filter(
        role__in=["cto", "ses_manager", "vp_player_agents", "president"]
    ).exists():
        return True
    # Player Agent can see their own division
    if division:
        return roles.filter(role="player_agent", division=division).exists()
    return False


def _get_checked_in_players(session):
    """Return PlayerSeason queryset of checked-in players for a session."""
    checkin_assignment_ids = CheckIn.objects.filter(
        session_assignment__session=session,
    ).values_list("session_assignment_id", flat=True)

    player_season_ids = session.assignments.filter(
        id__in=checkin_assignment_ids,
    ).values_list("player_season_id", flat=True)

    return (
        PlayerSeason.objects.filter(
            id__in=player_season_ids,
        )
        .select_related("player")
        .order_by("player__last_name", "player__first_name")
    )


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@login_required
def eval_home(request):
    """Station and session selector — entry point for station-mode evals."""
    if not _is_eval_authorized(request.user):
        return HttpResponseForbidden("You do not have permission to enter evaluations.")

    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        return render(
            request,
            "evaluations/station_home.html",
            {
                "stations": [],
                "sessions": [],
                "season": None,
            },
        )

    stations = Station.objects.filter(
        league=active_season.league,
        is_active=True,
    ).order_by("display_order")

    sessions = Session.objects.filter(
        season=active_season,
    ).order_by("-date", "start_time")

    return render(
        request,
        "evaluations/station_home.html",
        {
            "stations": stations,
            "sessions": sessions,
            "season": active_season,
        },
    )


@login_required
def station_eval(request, station_id):
    """Redirect: station selected, pick the most recent session automatically."""
    if not _is_eval_authorized(request.user):
        return HttpResponseForbidden("You do not have permission to enter evaluations.")

    station = get_object_or_404(Station, pk=station_id, is_active=True)
    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        raise Http404("No active season.")

    # Default to most recent session
    session = (
        Session.objects.filter(season=active_season)
        .order_by("-date", "-start_time")
        .first()
    )
    if not session:
        raise Http404("No sessions found.")

    return redirect(
        "evaluations:station_session_eval", station_id=station.pk, session_id=session.pk
    )


@login_required
def station_session_eval(request, station_id, session_id):
    """Player list for a station + session — the main workhorse view."""
    if not _is_eval_authorized(request.user):
        return HttpResponseForbidden("You do not have permission to enter evaluations.")

    station = get_object_or_404(Station, pk=station_id, is_active=True)
    session = get_object_or_404(Session, pk=session_id)
    coach_season = _get_coach_season(request.user, session)

    players = _get_checked_in_players(session)

    # Determine which players this coach has already evaluated at this station
    evaluated_ids = set()
    if coach_season:
        evaluated_ids = set(
            Evaluation.objects.filter(
                coach_season=coach_season,
                station=station,
                session=session,
            ).values_list("player_season_id", flat=True)
        )

    player_cards = []
    for ps in players:
        player_cards.append(
            {
                "player_season": ps,
                "evaluated": ps.pk in evaluated_ids,
            }
        )

    eval_count = len(evaluated_ids)
    total_count = len(player_cards)

    # All sessions for session switcher
    all_sessions = Session.objects.filter(
        season=session.season,
    ).order_by("-date", "start_time")

    # All stations for station switcher
    all_stations = Station.objects.filter(
        league=session.season.league,
        is_active=True,
    ).order_by("display_order")

    return render(
        request,
        "evaluations/station_players.html",
        {
            "station": station,
            "session": session,
            "player_cards": player_cards,
            "eval_count": eval_count,
            "total_count": total_count,
            "all_sessions": all_sessions,
            "all_stations": all_stations,
            "has_coach_season": coach_season is not None,
        },
    )


@login_required
def eval_player(request, station_id, session_id, player_season_id):
    """Evaluation form for a single player at a station."""
    if not _is_eval_authorized(request.user):
        return HttpResponseForbidden("You do not have permission to enter evaluations.")

    station = get_object_or_404(Station, pk=station_id, is_active=True)
    session = get_object_or_404(Session, pk=session_id)
    player_season = get_object_or_404(
        PlayerSeason.objects.select_related("player"), pk=player_season_id
    )
    coach_season = _get_coach_season(request.user, session)

    if not coach_season:
        return HttpResponseForbidden("You are not assigned as a coach for this season.")

    # Load existing evaluation if any (for pre-populating)
    existing_eval = Evaluation.objects.filter(
        coach_season=coach_season,
        station=station,
        session=session,
        player_season=player_season,
    ).first()

    existing_scores = existing_eval.scores if existing_eval else {}
    existing_notes = existing_eval.notes if existing_eval else ""

    # Build eval fields with existing values
    eval_fields = station.eval_fields or []
    for field in eval_fields:
        field["value"] = existing_scores.get(field["key"])

    # Find next unevaluated player
    players = _get_checked_in_players(session)
    evaluated_ids = set(
        Evaluation.objects.filter(
            coach_season=coach_season,
            station=station,
            session=session,
        ).values_list("player_season_id", flat=True)
    )
    # Add current player to evaluated set for "next" calculation
    evaluated_ids.add(player_season.pk)

    next_player = None
    for ps in players:
        if ps.pk not in evaluated_ids:
            next_player = ps
            break

    return render(
        request,
        "evaluations/eval_form.html",
        {
            "station": station,
            "session": session,
            "player_season": player_season,
            "eval_fields": eval_fields,
            "eval_fields_json": json.dumps(eval_fields),
            "existing_notes": existing_notes,
            "is_edit": existing_eval is not None,
            "next_player": next_player,
        },
    )


@login_required
def save_eval(request, station_id, session_id, player_season_id):
    """Save an evaluation (POST). HTMX-aware."""
    if request.method != "POST":
        return redirect(
            "evaluations:station_session_eval",
            station_id=station_id,
            session_id=session_id,
        )

    if not _is_eval_authorized(request.user):
        return HttpResponseForbidden("You do not have permission to enter evaluations.")

    station = get_object_or_404(Station, pk=station_id, is_active=True)
    session = get_object_or_404(Session, pk=session_id)
    player_season = get_object_or_404(PlayerSeason, pk=player_season_id)
    coach_season = _get_coach_season(request.user, session)

    if not coach_season:
        return HttpResponseForbidden("You are not assigned as a coach for this season.")

    # Build scores dict from POST data
    scores = {}
    eval_fields = station.eval_fields or []
    for field in eval_fields:
        key = field["key"]
        raw = request.POST.get(f"score_{key}", "").strip()
        if raw:
            try:
                scores[key] = int(raw)
            except (ValueError, TypeError):
                scores[key] = raw

    notes = request.POST.get("notes", "").strip()

    # Upsert evaluation
    eval_obj, _created = Evaluation.objects.update_or_create(
        coach_season=coach_season,
        station=station,
        session=session,
        player_season=player_season,
        defaults={
            "scores": scores,
            "notes": notes,
        },
    )

    # Check for "Save & Next" action
    action = request.POST.get("action", "save")

    # HTMX request — return partial card
    if request.headers.get("HX-Request"):
        return render(
            request,
            "evaluations/partials/player_eval_card.html",
            {
                "card": {
                    "player_season": player_season,
                    "evaluated": True,
                },
                "station": station,
                "session": session,
            },
        )

    # Regular POST
    if action == "save_next":
        # Find next unevaluated player
        players = _get_checked_in_players(session)
        evaluated_ids = set(
            Evaluation.objects.filter(
                coach_season=coach_season,
                station=station,
                session=session,
            ).values_list("player_season_id", flat=True)
        )

        for ps in players:
            if ps.pk not in evaluated_ids:
                return redirect(
                    "evaluations:eval_player",
                    station_id=station.pk,
                    session_id=session.pk,
                    player_season_id=ps.pk,
                )

    # No more players or regular save — back to player list
    return redirect(
        "evaluations:station_session_eval", station_id=station.pk, session_id=session.pk
    )


# ---------------------------------------------------------------------------
# Player-mode views (SFLL-70)
# ---------------------------------------------------------------------------


@login_required
def player_eval_view(request, player_season_id):
    """Show all evaluations for a specific player by the CURRENT coach only."""
    if not _is_eval_authorized(request.user):
        return HttpResponseForbidden("You do not have permission to view evaluations.")

    player_season = get_object_or_404(
        PlayerSeason.objects.select_related("player", "division", "season"),
        pk=player_season_id,
    )

    active_season = player_season.season
    coach_season = _get_coach_season_for_season(request.user, active_season)

    if not coach_season:
        return HttpResponseForbidden("You are not assigned as a coach for this season.")

    # PRIVACY: Only this coach's evaluations — never another coach's
    evals = (
        Evaluation.objects.filter(
            coach_season=coach_season,
            player_season=player_season,
        )
        .select_related("station", "session")
        .order_by("station__display_order", "-session__date")
    )

    # Group evaluations by station
    stations_data = defaultdict(list)
    for ev in evals:
        stations_data[ev.station].append(ev)

    # Get all stations for the league to show even unevaluated ones
    all_stations = Station.objects.filter(
        league=active_season.league,
        is_active=True,
    ).order_by("display_order")

    station_groups = []
    for station in all_stations:
        station_evals = stations_data.get(station, [])
        eval_fields = station.eval_fields or []
        # Pre-process: attach score_fields to each eval for easy template rendering
        processed_evals = []
        for ev in station_evals:
            score_fields = []
            for field in eval_fields:
                val = (ev.scores or {}).get(field["key"])
                score_fields.append(
                    {
                        "label": field.get("label", field["key"]),
                        "value": val,
                    }
                )
            processed_evals.append(
                {
                    "eval": ev,
                    "score_fields": score_fields,
                }
            )
        station_groups.append(
            {
                "station": station,
                "evaluations": processed_evals,
                "eval_fields": eval_fields,
            }
        )

    return render(
        request,
        "evaluations/player_eval.html",
        {
            "player_season": player_season,
            "station_groups": station_groups,
            "season": active_season,
            "coach_season": coach_season,
        },
    )


@login_required
def player_eval_edit(request, player_season_id, station_id, session_id):
    """Edit a coach's evaluation for a player at a specific station/session (from player mode)."""
    if not _is_eval_authorized(request.user):
        return HttpResponseForbidden("You do not have permission to enter evaluations.")

    station = get_object_or_404(Station, pk=station_id, is_active=True)
    session = get_object_or_404(Session, pk=session_id)
    player_season = get_object_or_404(
        PlayerSeason.objects.select_related("player"), pk=player_season_id
    )
    coach_season = _get_coach_season(request.user, session)

    if not coach_season:
        return HttpResponseForbidden("You are not assigned as a coach for this season.")

    # PRIVACY: Only load this coach's evaluation
    existing_eval = Evaluation.objects.filter(
        coach_season=coach_season,
        station=station,
        session=session,
        player_season=player_season,
    ).first()

    existing_scores = existing_eval.scores if existing_eval else {}
    existing_notes = existing_eval.notes if existing_eval else ""

    eval_fields = station.eval_fields or []
    for field in eval_fields:
        field["value"] = existing_scores.get(field["key"])

    if request.method == "POST":
        scores = {}
        for field in station.eval_fields or []:
            key = field["key"]
            raw = request.POST.get(f"score_{key}", "").strip()
            if raw:
                try:
                    scores[key] = int(raw)
                except (ValueError, TypeError):
                    scores[key] = raw

        notes = request.POST.get("notes", "").strip()

        Evaluation.objects.update_or_create(
            coach_season=coach_season,
            station=station,
            session=session,
            player_season=player_season,
            defaults={"scores": scores, "notes": notes},
        )
        return redirect("evaluations:player_eval", player_season_id=player_season.pk)

    return render(
        request,
        "evaluations/player_eval_edit.html",
        {
            "station": station,
            "session": session,
            "player_season": player_season,
            "eval_fields": eval_fields,
            "eval_fields_json": json.dumps(eval_fields),
            "existing_notes": existing_notes,
            "is_edit": existing_eval is not None,
        },
    )


@login_required
def my_evaluations(request):
    """Show all evaluations entered by the current coach, grouped by session then player."""
    if not _is_eval_authorized(request.user):
        return HttpResponseForbidden("You do not have permission to view evaluations.")

    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        return render(
            request,
            "evaluations/my_evals.html",
            {
                "session_groups": [],
                "season": None,
            },
        )

    coach_season = _get_coach_season_for_season(request.user, active_season)
    if not coach_season:
        return render(
            request,
            "evaluations/my_evals.html",
            {
                "session_groups": [],
                "season": active_season,
                "no_coach_season": True,
            },
        )

    # PRIVACY: Only this coach's evaluations
    evals = (
        Evaluation.objects.filter(
            coach_season=coach_season,
        )
        .select_related(
            "player_season__player",
            "player_season__division",
            "station",
            "session",
        )
        .order_by(
            "-session__date",
            "player_season__player__last_name",
            "station__display_order",
        )
    )

    # Group by session, then by player
    session_groups = defaultdict(lambda: defaultdict(list))
    for ev in evals:
        session_groups[ev.session][ev.player_season].append(ev)

    # Convert to ordered list for template
    grouped = []
    for session in sorted(session_groups.keys(), key=lambda s: s.date, reverse=True):
        players = []
        for ps in sorted(
            session_groups[session].keys(),
            key=lambda p: (p.player.last_name, p.player.first_name),
        ):
            players.append(
                {
                    "player_season": ps,
                    "evaluations": session_groups[session][ps],
                }
            )
        grouped.append(
            {
                "session": session,
                "players": players,
                "eval_count": sum(len(p["evaluations"]) for p in players),
            }
        )

    return render(
        request,
        "evaluations/my_evals.html",
        {
            "session_groups": grouped,
            "season": active_season,
            "total_evals": evals.count(),
        },
    )


# ---------------------------------------------------------------------------
# Aggregated report views (SFLL-71)
# ---------------------------------------------------------------------------


@login_required
def division_report(request, division_id):
    """Aggregated evaluation report for a division. Shows averages only — never individual coach scores."""
    division = get_object_or_404(Division, pk=division_id)

    if not _can_view_aggregated(request.user, division=division):
        return HttpResponseForbidden(
            "You do not have permission to view aggregated reports for this division."
        )

    active_season = Season.objects.filter(is_active=True).first()
    if not active_season:
        return render(
            request,
            "evaluations/division_report.html",
            {
                "division": division,
                "season": None,
                "player_rows": [],
                "stations": [],
            },
        )

    # All players in this division for the active season
    player_seasons = (
        PlayerSeason.objects.filter(
            season=active_season,
            division=division,
        )
        .select_related("player")
        .order_by("player__last_name", "player__first_name")
    )

    # All stations for this league
    stations = list(
        Station.objects.filter(
            league=active_season.league,
            is_active=True,
        ).order_by("display_order")
    )

    # Aggregate evaluations — NEVER expose individual coach scores
    # For each player x station, compute average across ALL coaches
    player_rows = []
    for ps in player_seasons:
        evals = Evaluation.objects.filter(
            player_season=ps,
        )
        total_eval_count = evals.count()

        # Build ordered list of station averages (matching stations list order)
        station_avg_list = []
        total_score_sum = 0
        total_score_count = 0

        for station in stations:
            station_evals = evals.filter(station=station)
            if not station_evals.exists():
                station_avg_list.append({"station": station, "avg": None})
                continue

            all_scores = []
            for ev in station_evals:
                for key, val in (ev.scores or {}).items():
                    if isinstance(val, (int, float)):
                        all_scores.append(val)

            if all_scores:
                avg = round(sum(all_scores) / len(all_scores), 1)
                station_avg_list.append({"station": station, "avg": avg})
                total_score_sum += sum(all_scores)
                total_score_count += len(all_scores)
            else:
                station_avg_list.append({"station": station, "avg": None})

        overall_avg = (
            round(total_score_sum / total_score_count, 1) if total_score_count else None
        )

        player_rows.append(
            {
                "player_season": ps,
                "station_avgs": station_avg_list,
                "overall_avg": overall_avg,
                "eval_count": total_eval_count,
            }
        )

    # Sort by overall average descending (None at the end)
    sort_by = request.GET.get("sort", "avg_desc")
    if sort_by == "avg_asc":
        player_rows.sort(
            key=lambda r: (r["overall_avg"] is None, r["overall_avg"] or 0)
        )
    elif sort_by == "name":
        player_rows.sort(
            key=lambda r: (
                r["player_season"].player.last_name,
                r["player_season"].player.first_name,
            )
        )
    elif sort_by == "evals":
        player_rows.sort(key=lambda r: r["eval_count"], reverse=True)
    else:  # avg_desc (default)
        player_rows.sort(
            key=lambda r: (r["overall_avg"] is None, -(r["overall_avg"] or 0))
        )

    return render(
        request,
        "evaluations/division_report.html",
        {
            "division": division,
            "season": active_season,
            "player_rows": player_rows,
            "stations": stations,
            "sort_by": sort_by,
        },
    )


@login_required
def player_report(request, player_season_id):
    """Aggregated evaluation report for a single player. Shows averages — never individual coach scores."""
    player_season = get_object_or_404(
        PlayerSeason.objects.select_related("player", "division", "season"),
        pk=player_season_id,
    )

    if not _can_view_aggregated(request.user, division=player_season.division):
        return HttpResponseForbidden(
            "You do not have permission to view aggregated reports for this player."
        )

    active_season = player_season.season
    stations = Station.objects.filter(
        league=active_season.league,
        is_active=True,
    ).order_by("display_order")

    # PRIVACY: aggregate only — never expose individual coach scores
    evals = Evaluation.objects.filter(player_season=player_season)

    station_reports = []
    for station in stations:
        station_evals = evals.filter(station=station)
        coach_count = station_evals.values("coach_season").distinct().count()

        if not station_evals.exists():
            station_reports.append(
                {
                    "station": station,
                    "eval_fields": station.eval_fields or [],
                    "field_stats": [],
                    "coach_count": 0,
                    "has_data": False,
                }
            )
            continue

        # Per-field stats
        field_stats = []
        for field_def in station.eval_fields or []:
            key = field_def["key"]
            values = []
            for ev in station_evals:
                val = (ev.scores or {}).get(key)
                if isinstance(val, (int, float)):
                    values.append(val)

            if values:
                field_stats.append(
                    {
                        "label": field_def.get("label", key),
                        "key": key,
                        "avg": round(sum(values) / len(values), 1),
                        "min": min(values),
                        "max": max(values),
                        "count": len(values),
                    }
                )
            else:
                field_stats.append(
                    {
                        "label": field_def.get("label", key),
                        "key": key,
                        "avg": None,
                        "min": None,
                        "max": None,
                        "count": 0,
                    }
                )

        station_reports.append(
            {
                "station": station,
                "eval_fields": station.eval_fields or [],
                "field_stats": field_stats,
                "coach_count": coach_count,
                "has_data": True,
            }
        )

    # Objective metrics for this player
    objective_metrics = ObjectiveMetric.objects.filter(
        player_season=player_season,
    ).order_by("metric_type", "-session__date")

    return render(
        request,
        "evaluations/player_report.html",
        {
            "player_season": player_season,
            "station_reports": station_reports,
            "objective_metrics": objective_metrics,
            "season": active_season,
            "total_evals": evals.count(),
            "total_coaches": evals.values("coach_season").distinct().count(),
        },
    )
