from django.urls import path

from . import views

app_name = "draft"

urlpatterns = [
    path("", views.draft_home, name="index"),
    path("rankings/", views.coach_rankings, name="rankings"),
    path("rankings/save/", views.save_rankings, name="save_rankings"),
    path("seeding/<int:division_id>/", views.seeding, name="seeding"),
    path("seeding/<int:division_id>/save/", views.save_seeding, name="save_seeding"),
    path("seeding/<int:division_id>/lock/", views.lock_seeding, name="lock_seeding"),
    # Live draft
    path("live/<int:session_id>/", views.draft_board, name="draft_board"),
    path("live/<int:session_id>/start/", views.start_draft, name="start_draft"),
    path("live/<int:session_id>/undo/", views.undo_pick, name="undo_pick"),
    path(
        "live/<int:session_id>/complete/", views.complete_draft, name="complete_draft"
    ),
    path(
        "live/<int:session_id>/rosters/",
        views.post_draft_rosters,
        name="post_draft_rosters",
    ),
]
