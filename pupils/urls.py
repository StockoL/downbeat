from django.urls import path

from assessment import feedback_views
from reports import views as report_views

from . import loan_views, views
from .missing_out import missing_out_page

urlpatterns = [
    path("", views.pupils_home, name="pupils_home"),
    path("loans/", loan_views.loans, name="loans"),
    path("loans/<uuid:pk>/return/", loan_views.loan_return, name="loan_return"),
    path("class/<uuid:pk>/", views.class_pupils, name="class_pupils"),
    path("class/<uuid:pk>/missing-out/", missing_out_page, name="class_missing_out"),
    path("class/<uuid:pk>/components/", feedback_views.class_components, name="class_components"),
    path("class/<uuid:pk>/self-peer/", feedback_views.class_self_peer, name="class_self_peer"),
    path("class/<uuid:pk>/judgements/", report_views.class_judgements, name="class_judgements"),
    path("<uuid:pk>/", views.pupil_page, name="pupil_page"),
    path("<uuid:pk>/export.json", views.pupil_export, name="pupil_export"),
    path("flags/<uuid:pk>/remove/", views.pupil_flag_remove, name="pupil_flag_remove"),
    path("<uuid:pupil_pk>/relationships/<uuid:pk>/remove/", views.relationship_remove, name="relationship_remove"),
]
