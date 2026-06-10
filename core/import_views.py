"""
Views for the SportsConnect CSV import system.

All views require the CTO role.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import UserRole
from core.importers import SportsConnectImporter
from core.models import ImportFlag, ImportRun
from core.tasks import sync_sportsconnect
from players.models import League, Season


def _require_cto(user):
    """Return True if user has the CTO role or is a superuser."""
    if user.is_superuser:
        return True
    return UserRole.objects.filter(user=user, role="cto", is_active=True).exists()


def cto_required(view_func):
    """Decorator: login required + CTO role check."""

    @login_required
    def wrapper(request, *args, **kwargs):
        if not _require_cto(request.user):
            messages.error(
                request, "You do not have permission to access the import system."
            )
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)

    wrapper.__name__ = view_func.__name__
    wrapper.__doc__ = view_func.__doc__
    return wrapper


# ------------------------------------------------------------------
# Import history
# ------------------------------------------------------------------


@cto_required
def import_history(request):
    """List all import runs with summary stats."""
    runs = ImportRun.objects.select_related("league").order_by("-created_at")
    return render(request, "core/imports/history.html", {"runs": runs})


# ------------------------------------------------------------------
# CSV upload
# ------------------------------------------------------------------


@cto_required
def import_upload(request):
    """Upload and process a SportsConnect CSV."""
    league = League.objects.first()
    seasons = (
        Season.objects.filter(league=league).order_by("-year", "season_type")
        if league
        else []
    )

    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        season_id = request.POST.get("season_id")

        if not csv_file:
            messages.error(request, "Please select a CSV file.")
            return redirect("import_upload")

        if not csv_file.name.lower().endswith(".csv"):
            messages.error(request, "Only CSV files are accepted.")
            return redirect("import_upload")

        if not season_id:
            messages.error(request, "Please select a season.")
            return redirect("import_upload")

        try:
            season = Season.objects.get(pk=season_id)
        except Season.DoesNotExist:
            messages.error(request, "Invalid season selected.")
            return redirect("import_upload")

        importer = SportsConnectImporter(
            league=season.league,
            season=season,
            user=request.user,
        )
        import_run = importer.run(csv_file)

        return render(
            request,
            "core/imports/results.html",
            {
                "import_run": import_run,
                "stats": importer.stats,
            },
        )

    return render(
        request,
        "core/imports/upload.html",
        {
            "seasons": seasons,
        },
    )


# ------------------------------------------------------------------
# Flag review
# ------------------------------------------------------------------


@cto_required
def import_review(request, run_id):
    """Review flagged records from an import run."""
    import_run = get_object_or_404(ImportRun, pk=run_id)

    flag_type_filter = request.GET.get("flag_type", "")
    flags = import_run.flags.select_related("player_season__player").order_by(
        "-created_at"
    )

    if flag_type_filter:
        flags = flags.filter(flag_type=flag_type_filter)

    flag_type_choices = ImportFlag._meta.get_field("flag_type").choices

    return render(
        request,
        "core/imports/review.html",
        {
            "import_run": import_run,
            "flags": flags,
            "flag_type_filter": flag_type_filter,
            "flag_type_choices": flag_type_choices,
        },
    )


# ------------------------------------------------------------------
# Resolve / dismiss flag
# ------------------------------------------------------------------


@cto_required
def resolve_flag(request, run_id, flag_id):
    """Mark an import flag as resolved."""
    import_run = get_object_or_404(ImportRun, pk=run_id)
    flag = get_object_or_404(ImportFlag, pk=flag_id, import_run=import_run)

    if request.method == "POST":
        action = request.POST.get("action", "resolve")
        notes = request.POST.get("notes", "")

        flag.resolved = True
        flag.resolved_by = request.user
        flag.resolved_at = timezone.now()
        flag.resolution_notes = notes if action == "resolve" else f"[Dismissed] {notes}"
        flag.save()

        messages.success(request, f"Flag #{flag.pk} {action}d.")
        return redirect("import_review", run_id=run_id)

    raise Http404


# ------------------------------------------------------------------
# Manual sync trigger
# ------------------------------------------------------------------


@cto_required
@require_POST
def import_trigger(request):
    """Trigger a SportsConnect sync via Celery for the active league."""
    league = League.objects.exclude(sportsconnect_report_url="").first()

    if not league:
        messages.error(request, "No league has a SportsConnect report URL configured.")
        return redirect("import_history")

    sync_sportsconnect.delay(league_id=league.pk)
    messages.success(
        request,
        f"SportsConnect sync queued for {league.name}. "
        "Results will appear in import history once complete.",
    )
    return redirect("import_history")
