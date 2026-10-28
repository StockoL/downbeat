"""The error pages and the safeguards around bad input: a plain page with a way back, never a bare default."""

import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory
from django.views import defaults

from rooms.models import SeatingPlan

pytestmark = pytest.mark.django_db


def test_an_unknown_address_has_a_way_back(client, timetable):
    response = client.get("/no-such-page/")
    page = response.content.decode()
    assert response.status_code == 404 and "Not found" in page and 'href="/"' in page and "Go back" in page


def test_a_deleted_row_is_not_found_too(client, timetable):
    response = client.get("/pupils/00000000-0000-0000-0000-000000000000/")
    assert response.status_code == 404 and "Not found" in response.content.decode()


def test_signed_out_an_unknown_address_still_asks_for_sign_in(anon_client, teacher, timetable):
    assert anon_client.get("/no-such-page/").url.startswith("/login/")


def test_the_server_error_page_needs_no_request(db):
    response = defaults.server_error(RequestFactory().get("/"))
    page = response.content.decode()
    assert response.status_code == 500 and "Something went wrong" in page and "downbeat.log" in page


def test_the_not_allowed_page(db):
    response = defaults.permission_denied(RequestFactory().get("/"), PermissionDenied())
    assert response.status_code == 403 and "Not allowed" in response.content.decode()


def test_a_malformed_id_is_bad_input_not_a_server_error(client, timetable, klass, room, pupils):
    plan = SeatingPlan.objects.create(klass=klass, room=room, name="Plan", active_from="2026-10-19")
    response = client.post(f"/plan/seating/{plan.pk}/move/", {"pupil": "not-an-id", "seat": "bin"})
    assert response.status_code == 400 and "Not understood" in response.content.decode()
    response = client.post(f"/pupils/class/{klass.pk}/reports/", {"pupil": "not-an-id", "text": "x"})
    assert response.status_code == 400


def test_an_expired_form_says_so(teacher, timetable):
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(teacher)
    response = browser.post("/settings/data/backup/")
    assert response.status_code == 403 and "This page had expired" in response.content.decode()


def test_every_page_carries_the_failed_request_line(client, timetable):
    page = client.get("/settings/").content.decode()
    assert "data-request-error hidden" in page and "hx-on::response-error" in page and "hx-on::send-error" in page


def test_a_whole_school_fits_in_one_form():
    assert settings.DATA_UPLOAD_MAX_NUMBER_FIELDS >= 10_000


def test_a_database_behind_the_code_says_what_to_run(client, timetable, monkeypatch):
    from core.middleware import PendingMigrationsMiddleware

    monkeypatch.setattr(PendingMigrationsMiddleware, "pending", staticmethod(lambda: True))
    response = client.get("/")
    page = response.content.decode()
    assert response.status_code == 503 and "manage.py migrate" in page and "Reload" in page


def test_an_up_to_date_database_is_checked_once(rf):
    from django.http import HttpResponse

    from core.middleware import PendingMigrationsMiddleware

    calls = []
    middleware = PendingMigrationsMiddleware(lambda request: HttpResponse("ok"))
    middleware.pending = lambda: calls.append(1) or False
    middleware(rf.get("/"))
    middleware(rf.get("/"))
    assert len(calls) == 1
