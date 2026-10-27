from django.urls import path

from notes import settings_views as note_settings

from . import rotation_views, views

urlpatterns = [
    path("timetable/", views.timetable_edit, name="timetable_edit"),
    path("slots/", views.slot_list, name="slot_list"),
    path("slots/<uuid:pk>/", views.slot_edit, name="slot_edit"),
    path("slots/<uuid:pk>/delete/", views.slot_delete, name="slot_delete"),
    path("classes/", views.class_list, name="class_list"),
    path("classes/<uuid:pk>/", views.class_detail, name="class_detail"),
    path("classes/<uuid:pk>/delete/", views.class_delete, name="class_delete"),
    path("classes/<uuid:pk>/remove/<uuid:pupil_pk>/", views.class_remove_pupil, name="class_remove_pupil"),
    path("pupils/", views.pupil_list, name="pupil_list"),
    path("pupils/<uuid:pk>/", views.pupil_edit, name="pupil_edit"),
    path("pupils/<uuid:pk>/delete/", views.pupil_delete, name="pupil_delete"),
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/generate/", views.session_generate, name="session_generate"),
    path("sessions/<uuid:pk>/", views.session_edit, name="session_edit"),
    path("sessions/<uuid:pk>/delete/", views.session_delete, name="session_delete"),
    path("note-types/", note_settings.note_types, name="note_types"),
    path("goals/", note_settings.goals, name="goals"),
    path("rotations/", rotation_views.rotation_list, name="rotation_list"),
    path("rotations/<uuid:pk>/", rotation_views.rotation_detail, name="rotation_detail"),
    path("rotations/<uuid:pk>/delete/", rotation_views.rotation_delete, name="rotation_delete"),
    path("rotations/assigned/<uuid:pk>/remove/", rotation_views.rotation_unassign, name="rotation_unassign"),
    path("checklist/", note_settings.checklist, name="checklist"),
]
