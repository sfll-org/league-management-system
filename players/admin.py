from django.contrib import admin
from .models import Division, Team, Player


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ('name', 'age_min', 'age_max')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'division', 'head_coach', 'season', 'year')
    list_filter = ('division', 'season', 'year')
    filter_horizontal = ('assistant_coaches',)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'date_of_birth', 'division', 'team', 'registration_status')
    list_filter = ('division', 'registration_status', 'gender')
    search_fields = ('first_name', 'last_name', 'parent_name', 'parent_email')
