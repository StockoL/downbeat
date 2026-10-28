from django.urls import path

from . import views

urlpatterns = [
    path("units/<uuid:pk>/assessment/", views.unit_assessment, name="unit_assessment"),
    path("units/<uuid:pk>/criteria.json", views.components_export, name="components_export"),
    path("units/<uuid:pk>/criteria/import/", views.components_import, name="components_import"),
    path("lessons/<uuid:pk>/hinge/copy/", views.hinge_copy, name="hinge_copy"),
]
