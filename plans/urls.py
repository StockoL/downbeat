from django.urls import path

from . import views

urlpatterns = [
    path("schemes/", views.schemes, name="schemes"),
    path("schemes/<uuid:pk>/", views.scheme, name="scheme"),
    path("units/<uuid:pk>/", views.unit, name="unit"),
    path("units/<uuid:pk>/lessons/", views.unit_add_lesson, name="unit_add_lesson"),
    path("units/<uuid:pk>/duplicate/", views.unit_duplicate, name="unit_duplicate"),
    path("units/<uuid:pk>/delete/", views.unit_delete, name="unit_delete"),
    path("lessons/<uuid:pk>/", views.lesson, name="lesson"),
    path("lessons/<uuid:pk>/delete/", views.lesson_delete, name="lesson_delete"),
    path("classes/<uuid:pk>/", views.class_lessons, name="class_lessons"),
    path("classes/<uuid:pk>/fill/", views.class_fill, name="class_fill"),
    path("sessions/<uuid:pk>/lesson/", views.session_set_lesson, name="session_set_lesson"),
]
