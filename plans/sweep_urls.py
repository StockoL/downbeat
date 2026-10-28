from django.urls import path

from assessment import feedback_views

from . import prep, sweep_views

urlpatterns = [
    path("", sweep_views.sweep_home, name="sweep_home"),
    path("prep/", prep.prep, name="prep"),
    path("prep/<uuid:pk>/add/", prep.prep_add, name="prep_add"),
    path("prep/items/<uuid:pk>/toggle/", prep.prep_toggle, name="prep_toggle"),
    path("prep/items/<uuid:pk>/remove/", prep.prep_remove, name="prep_remove"),
    path("<uuid:pk>/", sweep_views.session_sweep, name="session_sweep"),
    path("notes/<uuid:pk>/members/", sweep_views.give_to_members, name="give_to_members"),
    path("<uuid:pk>/feedback/", feedback_views.session_feedback, name="session_feedback"),
    path("feedback/<uuid:pk>/delete/", feedback_views.feedback_delete, name="feedback_delete"),
]
