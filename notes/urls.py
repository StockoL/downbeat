from django.urls import path

from . import views

urlpatterns = [
    path("<uuid:session_pk>/state/", views.state, name="lesson_state"),
    path("<uuid:session_pk>/inbox/<uuid:pupil_pk>/", views.inbox, name="inbox"),
]
