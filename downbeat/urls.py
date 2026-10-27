from django.urls import include, path

from assessment.views import bands, strands
from notes.views import sync_ops
from pupils.views import flag_types

urlpatterns = [
    path("", include("core.urls")),
    path("room/", include("notes.urls")),
    path("sync/", sync_ops, name="sync"),
    path("plan/", include("rooms.plan_urls")),
    path("plan/", include("plans.urls")),
    path("plan/", include("assessment.urls")),
    path("sweep/", include("plans.sweep_urls")),
    path("pupils/", include("pupils.urls")),
    path("settings/flags/", flag_types, name="flag_types"),
    path("settings/strands/", strands, name="strands"),
    path("settings/bands/", bands, name="bands"),
    path("settings/", include("timetable.urls")),
    path("settings/rooms/", include("rooms.urls")),
]
