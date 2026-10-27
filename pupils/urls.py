from django.urls import path

from . import views

urlpatterns = [
    path("", views.pupils_home, name="pupils_home"),
    path("class/<uuid:pk>/", views.class_pupils, name="class_pupils"),
    path("<uuid:pk>/", views.pupil_page, name="pupil_page"),
    path("flags/<uuid:pk>/remove/", views.pupil_flag_remove, name="pupil_flag_remove"),
    path("<uuid:pupil_pk>/relationships/<uuid:pk>/remove/", views.relationship_remove, name="relationship_remove"),
]
