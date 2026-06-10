from django.contrib import admin

from .models import CoachRanking, Evaluation, ObjectiveMetric


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("player_season", "session", "coach_season", "station", "created_at")
    list_filter = ("session", "station")
    search_fields = (
        "player_season__player__first_name",
        "player_season__player__last_name",
    )


@admin.register(ObjectiveMetric)
class ObjectiveMetricAdmin(admin.ModelAdmin):
    list_display = (
        "player_season",
        "session",
        "metric_type",
        "value",
        "unit",
        "recorded_by",
    )
    list_filter = ("metric_type", "session")
    search_fields = (
        "player_season__player__first_name",
        "player_season__player__last_name",
    )


@admin.register(CoachRanking)
class CoachRankingAdmin(admin.ModelAdmin):
    list_display = ("coach_season", "player_season", "rank_order")
    list_filter = ("coach_season",)
    search_fields = (
        "player_season__player__first_name",
        "player_season__player__last_name",
    )
