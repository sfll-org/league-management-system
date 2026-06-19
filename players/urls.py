from django.urls import path

from . import views

app_name = 'players'

urlpatterns = [
    path('', views.index, name='index'),
    path('teams/', views.teams, name='teams'),
    path('teams/<int:pk>/dugout-card/', views.dugout_card, name='dugout_card'),
    path('print/', views.print_index, name='print_index'),
    path('teams/<int:team_season_id>/print/', views.print_dugout_card, name='print_dugout_card'),
    path('families/', views.family_index, name='family_index'),
    path('families/<str:family_key>/', views.family_detail, name='family_detail'),
]
