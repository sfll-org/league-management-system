from django.urls import path

from . import views

app_name = 'tryouts'

urlpatterns = [
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/', views.session_detail, name='session_detail'),
    path('sessions/<int:pk>/edit/', views.session_edit, name='session_edit'),
    path('sessions/<int:pk>/delete/', views.session_delete, name='session_delete'),
    path('sessions/<int:pk>/assign/', views.session_assign_players, name='session_assign'),
    # Check-in
    path('sessions/<int:pk>/checkin/', views.session_checkin, name='session_checkin'),
    path('checkin/<uuid:token>/', views.checkin_by_token, name='checkin_by_token'),
    path('sessions/<int:pk>/checkin/search/', views.checkin_search, name='checkin_search'),
    path('sessions/<int:pk>/checkin/<int:assignment_id>/', views.checkin_player, name='checkin_player'),
    # Reassignment
    path('sessions/<int:pk>/reassign/<int:assignment_id>/', views.reassign_player, name='reassign_player'),
    # No-show flagging
    path('sessions/<int:pk>/noshows/', views.flag_noshows, name='flag_noshows'),
    # QR codes
    path('players/<int:player_season_id>/qr/', views.player_qr_code, name='player_qr_code'),
    path('sessions/<int:pk>/qrcodes/', views.session_qr_codes, name='session_qr_codes'),
    # Keep the index as a redirect to session_list
    path('', views.session_list, name='index'),
]
