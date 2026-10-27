from django.urls import path

from timetable import lesson_views

from . import pwa, views
from .auth_views import LoginView, LogoutView

urlpatterns = [
    path("", lesson_views.today, name="today"),
    path("room/<uuid:pk>/", lesson_views.room_view, name="room_view"),
    path("room/<uuid:pk>/projector/", lesson_views.projector, name="projector"),
    path("room/<uuid:pk>/cover.pdf", lesson_views.cover, name="cover_pdf"),
    path("manifest.webmanifest", pwa.manifest, name="manifest"),
    path("sw.js", pwa.service_worker, name="service_worker"),
    path("offline/", pwa.offline, name="offline"),
    path("setup/", views.setup, name="setup"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("settings/", views.settings_home, name="settings"),
    path("settings/data/", views.data_page, name="data_page"),
    path("settings/data/backup/", views.data_backup, name="data_backup"),
    path("settings/data/export/", views.data_export, name="data_export"),
    path("settings/data/delete-all/", views.data_delete_all, name="data_delete_all"),
]
