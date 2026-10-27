from django.urls import include, path

from notes.views import sync_ops
from pupils.views import flag_types

urlpatterns = [
    path("", include("core.urls")),
    path("room/", include("notes.urls")),
    path("sync/", sync_ops, name="sync"),
    path("plan/", include("rooms.plan_urls")),
    path("plan/", include("plans.urls")),
    path("pupils/", include("pupils.urls")),
    path("settings/flags/", flag_types, name="flag_types"),
    path("settings/", include("timetable.urls")),
    path("settings/rooms/", include("rooms.urls")),
]
