from django.urls import path

from . import views

app_name = 'evaluations'

urlpatterns = [
    # Station-mode (existing)
    path('', views.eval_home, name='index'),
    path('station/<int:station_id>/', views.station_eval, name='station_eval'),
    path('station/<int:station_id>/session/<int:session_id>/',
         views.station_session_eval, name='station_session_eval'),
    path('station/<int:station_id>/session/<int:session_id>/player/<int:player_season_id>/',
         views.eval_player, name='eval_player'),
    path('station/<int:station_id>/session/<int:session_id>/player/<int:player_season_id>/save/',
         views.save_eval, name='save_eval'),

    # Player-mode (SFLL-70)
    path('player/<int:player_season_id>/', views.player_eval_view, name='player_eval'),
    path('player/<int:player_season_id>/station/<int:station_id>/session/<int:session_id>/edit/',
         views.player_eval_edit, name='player_eval_edit'),
    path('my/', views.my_evaluations, name='my_evals'),

    # Aggregated reports (SFLL-71)
    path('reports/division/<int:division_id>/', views.division_report, name='division_report'),
    path('reports/player/<int:player_season_id>/', views.player_report, name='player_report'),
]
