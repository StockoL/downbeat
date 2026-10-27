from django.urls import include, path

from notes.views import sync_ops

urlpatterns = [
    path("", include("core.urls")),
    path("room/", include("notes.urls")),
    path("sync/", sync_ops, name="sync"),
    path("plan/", include("rooms.plan_urls")),
    path("settings/", include("timetable.urls")),
    path("settings/rooms/", include("rooms.urls")),
]
