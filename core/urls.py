from django.urls import path

from timetable import lesson_views

from . import views

urlpatterns = [
    path("", lesson_views.today, name="today"),
    path("room/<uuid:pk>/", lesson_views.room_view, name="room_view"),
    path("setup/", views.setup, name="setup"),
    path("settings/", views.settings_home, name="settings"),
]
