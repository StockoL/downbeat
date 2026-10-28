from django.urls import path

from assessment import feedback_views
from reports import evening_views, report_views
from reports import views as judgement_views

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
    path("class/<uuid:pk>/judgements/", judgement_views.class_judgements, name="class_judgements"),
    path("class/<uuid:pk>/reports/", report_views.class_reports, name="class_reports"),
    path("class/<uuid:pk>/reports.csv", report_views.reports_csv, name="reports_csv"),
    path("notes/<uuid:pk>/promote/", report_views.note_promote, name="note_promote"),
    path("evenings/", evening_views.evening_list, name="evening_list"),
    path("evenings/<uuid:pk>/", evening_views.evening, name="evening"),
    path("evenings/<uuid:pk>/book/", evening_views.evening_book, name="evening_book"),
    path("evenings/<uuid:pk>/slots/<uuid:slot_pk>/free/", evening_views.evening_unbook, name="evening_unbook"),
    path("evenings/<uuid:pk>/import/", evening_views.evening_import, name="evening_import"),
    path("evenings/<uuid:pk>/delete/", evening_views.evening_delete, name="evening_delete"),
    path("evenings/<uuid:pk>/tonight/", evening_views.tonight, name="tonight"),
    path("evenings/<uuid:pk>/tonight/<uuid:slot_pk>/", evening_views.tonight_mark, name="tonight_mark"),
    path("<uuid:pk>/book/", evening_views.book_pupil, name="book_pupil"),
    path("<uuid:pk>/", views.pupil_page, name="pupil_page"),
    path("<uuid:pk>/export.json", views.pupil_export, name="pupil_export"),
    path("flags/<uuid:pk>/remove/", views.pupil_flag_remove, name="pupil_flag_remove"),
    path("<uuid:pupil_pk>/relationships/<uuid:pk>/remove/", views.relationship_remove, name="relationship_remove"),
]
