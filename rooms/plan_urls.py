from django.urls import path

from . import plan_views

urlpatterns = [
    path("", plan_views.plan_home, name="plan_home"),
    path("seating/new/", plan_views.seating_create, name="seating_create"),
    path("seating/<uuid:pk>/", plan_views.seating_edit, name="seating_edit"),
    path("seating/<uuid:pk>/move/", plan_views.seating_move, name="seating_move"),
    path("seating/<uuid:pk>/lock/", plan_views.seating_lock, name="seating_lock"),
    path("seating/<uuid:pk>/undo/", plan_views.seating_undo, name="seating_undo"),
    path("seating/<uuid:pk>/shuffle/", plan_views.seating_shuffle, name="seating_shuffle"),
    path("seating/<uuid:pk>/duplicate/", plan_views.seating_duplicate, name="seating_duplicate"),
    path("seating/<uuid:pk>/delete/", plan_views.seating_delete, name="seating_delete"),
]
