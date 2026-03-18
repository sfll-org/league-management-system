from django.contrib import admin
from .models import EvaluationCriteria, Evaluation, CoachRanking


@admin.register(EvaluationCriteria)
class EvaluationCriteriaAdmin(admin.ModelAdmin):
    list_display = ('name', 'division', 'min_score', 'max_score', 'weight')
    list_filter = ('division',)


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('player', 'session', 'station', 'evaluator', 'created_at')
    list_filter = ('session', 'station')
    search_fields = ('player__first_name', 'player__last_name')


@admin.register(CoachRanking)
class CoachRankingAdmin(admin.ModelAdmin):
    list_display = ('coach', 'player', 'division', 'rank', 'season', 'year')
    list_filter = ('division', 'season', 'year')
