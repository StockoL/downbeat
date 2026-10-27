from django.urls import path

from . import views

urlpatterns = [
    path("", views.today, name="today"),
    path("setup/", views.setup, name="setup"),
    path("settings/", views.settings_home, name="settings"),
]
