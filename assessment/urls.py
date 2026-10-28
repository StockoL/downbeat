from django.urls import path

from . import feedback_views, views

urlpatterns = [
    path("units/<uuid:pk>/assessment/", views.unit_assessment, name="unit_assessment"),
    path("units/<uuid:pk>/criteria.json", views.components_export, name="components_export"),
    path("units/<uuid:pk>/criteria/import/", views.components_import, name="components_import"),
    path("lessons/<uuid:pk>/hinge/copy/", views.hinge_copy, name="hinge_copy"),
    path("units/<uuid:pk>/codes/", feedback_views.codes_slide, name="codes_slide"),
    path("units/<uuid:pk>/exemplars/", views.exemplar_add, name="exemplar_add"),
    path("exemplars/<uuid:pk>/delete/", views.exemplar_delete, name="exemplar_delete"),
]
