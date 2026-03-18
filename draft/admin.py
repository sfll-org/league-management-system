from django.contrib import admin
from .models import DraftConfiguration, DraftPick, PlayerAgent


@admin.register(DraftConfiguration)
class DraftConfigurationAdmin(admin.ModelAdmin):
    list_display = ('division', 'season', 'year', 'num_rounds', 'snake_order', 'status')
    list_filter = ('status', 'division', 'year')


@admin.register(DraftPick)
class DraftPickAdmin(admin.ModelAdmin):
    list_display = ('config', 'round', 'pick_number', 'team', 'player', 'picked_at')
    list_filter = ('config', 'round')


@admin.register(PlayerAgent)
class PlayerAgentAdmin(admin.ModelAdmin):
    list_display = ('player', 'config', 'is_seeded', 'seeded_to_team')
    list_filter = ('config', 'is_seeded')
