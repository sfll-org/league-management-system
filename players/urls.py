from django.urls import path

from . import views

app_name = "players"

urlpatterns = [
    path("", views.index, name="index"),
    path("teams/", views.teams, name="teams"),
    path("teams/<int:pk>/dugout-card/", views.dugout_card, name="dugout_card"),
]
