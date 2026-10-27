from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("room/", include("notes.urls")),
    path("plan/", include("rooms.plan_urls")),
    path("settings/", include("timetable.urls")),
    path("settings/rooms/", include("rooms.urls")),
]
