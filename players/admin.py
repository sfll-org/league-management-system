from django.contrib import admin

from .models import (
    Division, League, Player, PlayerSeason, Season, Station, Team, TeamSeason,
)


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'domain', 'timezone')
    search_fields = ('name', 'short_name')


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'league', 'year', 'season_type', 'is_active', 'registration_open', 'draft_complete')
    list_filter = ('league', 'is_active', 'season_type', 'year')


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ('name', 'league', 'display_order', 'has_leagues', 'is_active')
    list_filter = ('league', 'is_active')
    ordering = ('display_order',)


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'league', 'display_order', 'is_active')
    list_filter = ('league', 'is_active')
    ordering = ('display_order',)


class PlayerSeasonInline(admin.TabularInline):
    model = PlayerSeason
    extra = 0
    fields = ('season', 'division', 'assigned_team', 'status', 'is_protected', 'is_top_4')


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'league', 'sportsconnect_player_id', 'date_of_birth')
    list_filter = ('league',)
    search_fields = ('first_name', 'last_name', 'sportsconnect_player_id')
    inlines = [PlayerSeasonInline]


@admin.register(PlayerSeason)
class PlayerSeasonAdmin(admin.ModelAdmin):
    list_display = ('player', 'season', 'division', 'assigned_team', 'status', 'is_protected', 'is_top_4', 'photo_release', 'medical_form', 'balance_outstanding')
    list_filter = ('season', 'division', 'status', 'is_protected', 'is_top_4', 'photo_release', 'medical_form')
    search_fields = ('player__first_name', 'player__last_name', 'account_email')
    fieldsets = (
        (None, {'fields': ('player', 'season', 'division', 'assigned_team', 'coaches_child_of', 'status', 'is_protected', 'is_top_4', 'draft_slot')}),
        ('SportsConnect', {'fields': ('account_name', 'account_email', 'additional_email', 'order_id', 'sportsconnect_order_detail_id')}),
        ('Compliance', {'fields': ('photo_release', 'medical_form', 'balance_outstanding'), 'description': 'Manually entered until SportsConnect API audit (SFLL-120).'}),
        ('Tokens', {'fields': ('rsvp_token', 'checkin_token'), 'classes': ('collapse',)}),
    )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'league')
    list_filter = ('league',)
    search_fields = ('name',)


@admin.register(TeamSeason)
class TeamSeasonAdmin(admin.ModelAdmin):
    list_display = ('team', 'season', 'division', 'sub_league', 'drafter')
    list_filter = ('season', 'division', 'sub_league')
    search_fields = ('team__name',)
