from django.contrib import admin

from .models import DraftPick, DraftSession


class DraftPickInline(admin.TabularInline):
    model = DraftPick
    extra = 0
    readonly_fields = ("picked_at",)


@admin.register(DraftSession)
class DraftSessionAdmin(admin.ModelAdmin):
    list_display = (
        "division",
        "sub_league",
        "season",
        "status",
        "current_round",
        "current_pick",
    )
    list_filter = ("status", "season", "division")
    inlines = [DraftPickInline]


@admin.register(DraftPick)
class DraftPickAdmin(admin.ModelAdmin):
    list_display = (
        "draft_session",
        "round_number",
        "pick_number",
        "team_season",
        "player_season",
        "is_top_4",
        "is_coaches_child",
        "picked_at",
    )
    list_filter = ("draft_session", "round_number", "is_top_4", "is_coaches_child")
    search_fields = (
        "player_season__player__first_name",
        "player_season__player__last_name",
    )
