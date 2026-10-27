from django.urls import path

from . import sweep_views

urlpatterns = [
    path("", sweep_views.sweep_home, name="sweep_home"),
    path("<uuid:pk>/", sweep_views.session_sweep, name="session_sweep"),
    path("notes/<uuid:pk>/members/", sweep_views.give_to_members, name="give_to_members"),
]
