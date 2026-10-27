from django.urls import path

from . import views

urlpatterns = [
    path("<uuid:session_pk>/sheet/<uuid:pupil_pk>/", views.note_sheet, name="note_sheet"),
    path("<uuid:session_pk>/inbox/<uuid:pupil_pk>/", views.inbox, name="inbox"),
    path("<uuid:session_pk>/notes/", views.note_add, name="note_add"),
    path("<uuid:session_pk>/notes/undo/", views.note_undo, name="note_undo"),
    path("<uuid:session_pk>/actions/", views.actions_sheet, name="actions_sheet"),
    path("<uuid:session_pk>/spoken/", views.spoken_toggle, name="spoken_toggle"),
    path("<uuid:session_pk>/absent/", views.absent_toggle, name="absent_toggle"),
    path("<uuid:session_pk>/pick/", views.pick, name="pick"),
    path("notes/<uuid:pk>/remove/", views.note_remove, name="note_remove"),
    path("notes/<uuid:pk>/done/", views.action_done, name="action_done"),
]
