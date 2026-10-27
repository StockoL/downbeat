from django.urls import path

from . import loan_views, views
from .missing_out import missing_out_page

urlpatterns = [
    path("", views.pupils_home, name="pupils_home"),
    path("loans/", loan_views.loans, name="loans"),
    path("loans/<uuid:pk>/return/", loan_views.loan_return, name="loan_return"),
    path("class/<uuid:pk>/", views.class_pupils, name="class_pupils"),
    path("class/<uuid:pk>/missing-out/", missing_out_page, name="class_missing_out"),
    path("<uuid:pk>/", views.pupil_page, name="pupil_page"),
    path("flags/<uuid:pk>/remove/", views.pupil_flag_remove, name="pupil_flag_remove"),
    path("<uuid:pupil_pk>/relationships/<uuid:pk>/remove/", views.relationship_remove, name="relationship_remove"),
]
