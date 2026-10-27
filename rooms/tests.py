import datetime

import pytest

from rooms.models import SEAT_HEIGHT, SEAT_WIDTH, Room, Seat
from timetable.models import Session

pytestmark = pytest.mark.django_db


@pytest.fixture
def seat(room):
    return Seat.objects.create(room=room, x=100, y=100, label="1")


def test_room_pages_render(client, timetable, seat):
    assert client.get("/settings/rooms/").status_code == 200
    response = client.get(f"/settings/rooms/{seat.room.pk}/")
    assert response.status_code == 200
    assert b'data-canvas="room"' in response.content


def test_add_room(client, timetable):
    response = client.post("/settings/rooms/", {"name": "Hall", "canvas_width": "900", "canvas_height": "600"})
    room = Room.objects.get()
    assert response.url == f"/settings/rooms/{room.pk}/"


def test_edit_room_rejects_silly_canvas(client, timetable, room):
    client.post(f"/settings/rooms/{room.pk}/", {"name": "M2", "canvas_width": "50", "canvas_height": "600"})
    room.refresh_from_db()
    assert room.canvas_width == 900


def test_add_seats_in_a_row_with_numbered_labels(client, timetable, room):
    client.post(f"/settings/rooms/{room.pk}/seats/", {"count": "3"})
    seats = list(room.seats.order_by("x"))
    assert [s.label for s in seats] == ["1", "2", "3"]
    assert len({s.y for s in seats}) == 1
    assert all(s.x + SEAT_WIDTH <= room.canvas_width for s in seats)


def test_added_seats_wrap_and_stay_on_the_canvas(client, timetable, room):
    client.post(f"/settings/rooms/{room.pk}/seats/", {"count": "40"})
    for seat in room.seats.all():
        assert seat.x + SEAT_WIDTH <= room.canvas_width
        assert seat.y + SEAT_HEIGHT <= room.canvas_height


def test_move_seat(client, timetable, seat):
    response = client.post(f"/settings/rooms/seats/{seat.pk}/", {"x": "300", "y": "210.4"})
    assert response.json()["x"] == 300
    seat.refresh_from_db()
    assert (seat.x, seat.y) == (300, 210)


def test_move_seat_is_clamped_to_the_canvas(client, timetable, seat):
    client.post(f"/settings/rooms/seats/{seat.pk}/", {"x": "5000", "y": "-20"})
    seat.refresh_from_db()
    assert (seat.x, seat.y) == (seat.room.canvas_width - SEAT_WIDTH, 0)


def test_paint_zone_and_near_teacher(client, timetable, seat):
    client.post(f"/settings/rooms/seats/{seat.pk}/", {"zone": "keyboard"})
    client.post(f"/settings/rooms/seats/{seat.pk}/", {"near_teacher": "1"})
    seat.refresh_from_db()
    assert seat.zone == "keyboard" and seat.near_teacher
    client.post(f"/settings/rooms/seats/{seat.pk}/", {"zone": ""})
    seat.refresh_from_db()
    assert seat.zone == ""


def test_unknown_zone_is_refused(client, timetable, seat):
    assert client.post(f"/settings/rooms/seats/{seat.pk}/", {"zone": "balcony"}).status_code == 400


def test_relabel_seat(client, timetable, seat):
    client.post(f"/settings/rooms/seats/{seat.pk}/", {"label": "  Piano 1 "})
    seat.refresh_from_db()
    assert seat.label == "Piano 1"


def test_delete_seat(client, timetable, seat):
    client.post(f"/settings/rooms/seats/{seat.pk}/delete/")
    assert not Seat.objects.exists()


def test_move_teacher_marker(client, timetable, room):
    client.post(f"/settings/rooms/{room.pk}/teacher/", {"x": "450", "y": "580"})
    room.refresh_from_db()
    assert (room.teacher_x, room.teacher_y) == (450, 580)


def test_delete_room_with_seats(client, timetable, seat):
    client.post(f"/settings/rooms/{seat.room.pk}/delete/")
    assert not Room.objects.exists() and not Seat.objects.exists()


def test_delete_room_in_use_is_refused(client, timetable, room, klass):
    Session.objects.create(date=datetime.date(2026, 11, 2), period="P1", room=room, klass=klass)
    client.post(f"/settings/rooms/{room.pk}/delete/")
    assert Room.objects.exists()
