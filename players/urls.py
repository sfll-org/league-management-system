from django.urls import path

from . import views

app_name = 'players'

urlpatterns = [
    path('', views.index, name='index'),
    path('teams/', views.teams, name='teams'),
    path('print/', views.print_index, name='print_index'),
    path(
        'teams/<int:team_season_id>/print/',
        views.print_dugout_card,
        name='print_dugout_card',
    ),
]
