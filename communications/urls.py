from django.urls import path

from . import views

app_name = 'communications'

urlpatterns = [
    path('', views.comms_home, name='index'),
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/preview/', views.template_preview, name='template_preview'),
    path('send/', views.compose_send, name='compose'),
    path('send/preview/', views.send_preview, name='send_preview'),
    path('send/confirm/', views.send_confirm, name='send_confirm'),
    path('log/', views.email_log, name='email_log'),
    path('rsvp-dashboard/', views.rsvp_dashboard, name='rsvp_dashboard'),
]
