import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from conftest import PASSWORD
from core.tests.test_setup import setup_post
from timetable.models import Timetable

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fresh_lockouts():
    cache.clear()
    yield
    cache.clear()


# --- First run, before any account exists ---

def test_with_no_account_every_page_leads_to_setup(anon_client):
    assert anon_client.get("/").url == "/setup/"
    assert anon_client.get("/settings/").url == "/setup/"
    html = anon_client.get("/setup/").content.decode()
    assert 'name="account-username"' in html


def test_setup_creates_the_account_and_signs_in(anon_client):
    data = setup_post(**{
        "account-username": "teacher", "account-password1": "a good long password", "account-password2": "a good long password",
    })
    response = anon_client.post("/setup/", data)
    assert response.url == "/"
    assert get_user_model().objects.get().username == "teacher"
    assert anon_client.get("/").status_code == 200  # signed in now


def test_setup_refuses_a_short_password_and_saves_nothing(anon_client):
    data = setup_post(**{"account-username": "teacher", "account-password1": "short", "account-password2": "short"})
    anon_client.post("/setup/", data)
    assert not get_user_model().objects.exists() and not Timetable.objects.exists()


def test_signed_in_setup_has_no_account_section(client):
    assert 'name="account-username"' not in client.get("/setup/").content.decode()


# --- Once an account exists ---

def test_signed_out_pages_go_to_login_with_next(anon_client, teacher, timetable):
    response = anon_client.get("/settings/pupils/?year=8")
    assert response.url == "/login/?next=%2Fsettings%2Fpupils%2F%3Fyear%3D8"


def test_setup_is_closed_to_strangers_once_an_account_exists(anon_client, teacher):
    assert anon_client.get("/setup/").url.startswith("/login/")
    anon_client.post("/setup/", setup_post())
    assert not Timetable.objects.exists()


def test_signed_out_htmx_request_moves_the_whole_page(anon_client, teacher, timetable):
    response = anon_client.get("/settings/", HTTP_HX_REQUEST="true")
    assert response.status_code == 204
    assert response["HX-Redirect"].startswith("/login/")


def test_static_and_pwa_files_need_no_sign_in(anon_client, teacher):
    assert anon_client.get("/static/js/htmx.min.js").status_code == 200
    assert anon_client.get("/login/").status_code == 200


def test_login_and_logout(anon_client, teacher, timetable):
    response = anon_client.post("/login/", {"username": "teacher", "password": PASSWORD, "next": "/settings/"})
    assert response.url == "/settings/"
    assert anon_client.get("/settings/").status_code == 200
    anon_client.post("/logout/")
    assert anon_client.get("/settings/").url.startswith("/login/")


def test_login_pauses_after_five_wrong_passwords(anon_client, teacher, timetable):
    for _ in range(5):
        anon_client.post("/login/", {"username": "teacher", "password": "wrong"})
    response = anon_client.post("/login/", {"username": "teacher", "password": PASSWORD})
    assert response.status_code == 200 and b"Too many wrong passwords" in response.content
    assert anon_client.get("/settings/").url.startswith("/login/")


def test_login_rejects_an_off_site_next(anon_client, teacher, timetable):
    response = anon_client.post("/login/", {"username": "teacher", "password": PASSWORD, "next": "https://example.com/"})
    assert response.url == "/"


# --- Upgrading an install from before sign-in ---

def test_install_with_a_timetable_but_no_account_asks_only_for_the_account(anon_client, timetable):
    assert anon_client.get("/").url == "/setup/"
    html = anon_client.get("/setup/").content.decode()
    assert 'name="account-username"' in html and 'name="timetable-name"' not in html
    response = anon_client.post("/setup/", {
        "account-username": "teacher", "account-password1": "a good long password", "account-password2": "a good long password",
    })
    assert response.url == "/"
    assert anon_client.get("/").status_code == 200
    assert Timetable.objects.get() == timetable
