import pytest

from notes.models import NoteType
from rooms.models import Room
from timetable.models import Timetable

pytestmark = pytest.mark.django_db


def setup_post(**overrides):
    """A valid setup submission: two periods, two note types, one room."""
    data = {
        "timetable-name": "2026–27",
        "timetable-week_cycle": "2",
        "periods-TOTAL_FORMS": "8",
        "periods-INITIAL_FORMS": "0",
        "periods-MIN_NUM_FORMS": "1",
        "periods-MAX_NUM_FORMS": "1000",
        "periods-0-label": "P2",
        "periods-0-start": "09:50",
        "periods-0-end": "10:50",
        "periods-1-label": "P1",
        "periods-1-start": "08:50",
        "periods-1-end": "09:50",
        "notetypes-TOTAL_FORMS": "6",
        "notetypes-INITIAL_FORMS": "0",
        "notetypes-MIN_NUM_FORMS": "1",
        "notetypes-MAX_NUM_FORMS": "1000",
        "notetypes-0-label": "House point",
        "notetypes-0-icon": "★",
        "notetypes-0-is_house_point": "on",
        "notetypes-1-label": "Chase homework",
        "notetypes-1-is_actionable_default": "on",
        "room-name": "M2",
    }
    data.update(overrides)
    return data


def test_no_values_are_seeded():
    assert not Timetable.objects.exists()
    assert not NoteType.objects.exists()
    assert not Room.objects.exists()


@pytest.mark.parametrize("url", ["/", "/settings/"])
def test_every_page_redirects_to_setup_until_a_timetable_exists(client, url):
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == "/setup/"


def test_setup_page_renders(client):
    assert client.get("/setup/").status_code == 200


def test_setup_creates_timetable_note_types_and_room(client):
    response = client.post("/setup/", setup_post())
    assert response.status_code == 302 and response.url == "/"

    timetable = Timetable.objects.get()
    assert timetable.week_cycle == 2
    assert [p["label"] for p in timetable.periods] == ["P1", "P2"]  # sorted by start
    assert timetable.periods[0] == {"label": "P1", "start": "08:50", "end": "09:50"}

    house_point, chase = NoteType.objects.all()
    assert house_point.label == "House point" and house_point.is_house_point and house_point.order == 0
    assert chase.is_actionable_default and not chase.is_house_point and chase.order == 1

    assert Room.objects.get().name == "M2"
    assert client.get("/").status_code == 200


def test_setup_saves_nothing_when_any_part_is_invalid(client):
    response = client.post("/setup/", setup_post(**{"room-name": ""}))
    assert response.status_code == 200
    assert not Timetable.objects.exists()
    assert not NoteType.objects.exists()


def test_setup_needs_at_least_one_period(client):
    blank = {f"periods-{i}-{f}": "" for i in (0, 1) for f in ("label", "start", "end")}
    client.post("/setup/", setup_post(**blank))
    assert not Timetable.objects.exists()


def test_setup_rejects_a_period_that_ends_before_it_starts(client):
    client.post("/setup/", setup_post(**{"periods-0-end": "09:00"}))
    assert not Timetable.objects.exists()


def test_setup_is_closed_once_done(client, timetable):
    response = client.get("/setup/")
    assert response.status_code == 302 and response.url == "/"
