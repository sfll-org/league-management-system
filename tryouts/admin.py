from django.contrib import admin
from .models import TryoutSession, Station, CheckIn


class StationInline(admin.TabularInline):
    model = Station
    extra = 1


@admin.register(TryoutSession)
class TryoutSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'division', 'date', 'start_time', 'end_time', 'location', 'status')
    list_filter = ('status', 'division', 'date')
    inlines = [StationInline]


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'session', 'order', 'evaluator')
    list_filter = ('session',)


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ('player', 'session', 'status', 'checked_in_at', 'checked_in_by')
    list_filter = ('status', 'session')
    search_fields = ('player__first_name', 'player__last_name')
