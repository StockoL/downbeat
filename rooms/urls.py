from django.urls import path

from . import views

urlpatterns = [
    path("", views.room_list, name="room_list"),
    path("<uuid:pk>/", views.room_edit, name="room_edit"),
    path("<uuid:pk>/delete/", views.room_delete, name="room_delete"),
    path("<uuid:pk>/seats/", views.seats_add, name="seats_add"),
    path("<uuid:pk>/teacher/", views.teacher_move, name="teacher_move"),
    path("seats/<uuid:pk>/", views.seat_update, name="seat_update"),
    path("seats/<uuid:pk>/delete/", views.seat_delete, name="seat_delete"),
]
