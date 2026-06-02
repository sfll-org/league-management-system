from django.contrib import admin

from .models import CheckIn, Session, SessionAssignment, WalkIn


class SessionAssignmentInline(admin.TabularInline):
    model = SessionAssignment
    extra = 0


class CheckInInline(admin.TabularInline):
    model = CheckIn
    extra = 0


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'season', 'division', 'date', 'start_time', 'end_time', 'location', 'is_makeup')
    list_filter = ('season', 'division', 'is_makeup', 'date')
    search_fields = ('name', 'location')
    inlines = [SessionAssignmentInline]


@admin.register(SessionAssignment)
class SessionAssignmentAdmin(admin.ModelAdmin):
    list_display = ('session', 'player_season', 'assigned_by', 'created_at')
    list_filter = ('session',)
    search_fields = ('player_season__player__first_name', 'player_season__player__last_name')


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ('session_assignment', 'checked_in_at', 'checked_in_by')
    list_filter = ('checked_in_at',)


@admin.register(WalkIn)
class WalkInAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'division', 'session', 'logged_at', 'logged_by')
    list_filter = ('division', 'logged_at')
    search_fields = ('first_name', 'last_name', 'notes')
    readonly_fields = ('logged_at',)
