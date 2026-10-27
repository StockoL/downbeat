import datetime

import pytest
from django.utils import timezone

from rooms.models import Room, Seat, SeatAssignment, SeatingPlan
from timetable.models import Session, Timetable
from timetable.services import live_session, next_session, sessions_on

pytestmark = pytest.mark.django_db


@pytest.fixture
def day_timetable(db):
    return Timetable.objects.create(name="Day", periods=[
        {"label": "P1", "start": "08:50", "end": "09:50"},
        {"label": "P2", "start": "09:50", "end": "10:50"},
        {"label": "P10", "start": "15:00", "end": "16:00"},
    ])


@pytest.fixture
def all_day(db):
    """A period that covers the whole day, so 'now' is always inside it."""
    return Timetable.objects.create(name="All day", periods=[{"label": "All", "start": "00:00", "end": "23:59"}])


def make(klass, room, date, period, status=Session.PLANNED):
    return Session.objects.create(date=date, period=period, klass=klass, room=room, status=status)


D = datetime.date(2026, 11, 2)


def at(date, hh, mm):
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hh, mm)))


# --- Services ---

def test_sessions_are_in_timetable_order_not_alphabetical(day_timetable, klass, room):
    make(klass, room, D, "P10")
    make(klass, room, D, "P2")
    make(klass, room, D, "P1")
    assert [s.period for s in sessions_on(D, day_timetable)] == ["P1", "P2", "P10"]


def test_live_session(day_timetable, klass, room):
    p1 = make(klass, room, D, "P1")
    assert live_session(at(D, 9, 0), day_timetable) == p1
    assert live_session(at(D, 9, 50), day_timetable) is None  # P2 has no session
    assert live_session(at(D, 8, 0), day_timetable) is None


def test_cancelled_session_is_never_live(day_timetable, klass, room):
    make(klass, room, D, "P1", Session.CANCELLED)
    assert live_session(at(D, 9, 0), day_timetable) is None


def test_next_session_later_today_then_another_day_skipping_cancelled(day_timetable, klass, room):
    p1 = make(klass, room, D, "P1")
    make(klass, room, D, "P2", Session.CANCELLED)
    p10 = make(klass, room, D, "P10")
    tomorrow = make(klass, room, D + datetime.timedelta(days=1), "P1")
    assert next_session(p1, day_timetable) == p10
    assert next_session(p10, day_timetable) == tomorrow
    assert next_session(tomorrow, day_timetable) is None


# --- Today ---

def test_today_goes_straight_to_the_live_session(client, all_day, klass, room):
    session = make(klass, room, timezone.localdate(), "All")
    response = client.get("/")
    assert response.status_code == 302 and response.url == f"/room/{session.pk}/"


def test_today_list_on_request_even_when_live(client, all_day, klass, room):
    make(klass, room, timezone.localdate(), "All")
    response = client.get("/?list")
    assert response.status_code == 200 and b"8X Mu" in response.content


def test_today_lists_sessions_when_none_is_live(client, timetable, klass, room):
    make(klass, room, timezone.localdate(), "Gone")  # a period the timetable no longer has is never live
    response = client.get("/")
    assert response.status_code == 200 and b"8X Mu" in response.content


def test_today_with_nothing_on_names_the_next_session(client, timetable, klass, room):
    make(klass, room, timezone.localdate() + datetime.timedelta(days=3), "P1")
    response = client.get("/")
    assert b"Nothing timetabled today" in response.content and b"8X Mu" in response.content


# --- Room view ---

def test_room_view_shows_the_plan_names_and_no_prompts(client, timetable, klass, room, pupils):
    seat = Seat.objects.create(room=room, x=0, y=0)
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=D)
    SeatAssignment.objects.create(seating_plan=plan, seat=seat, pupil=pupils[0])
    session = make(klass, room, D, "P1")
    html = client.get(f"/room/{session.pk}/").content.decode()
    assert "Aleya K" in html
    assert "hasn't been seated" not in html
    assert 'data-canvas="view"' in html


def test_room_view_links_the_next_session(client, timetable, klass, room):
    session = make(klass, room, D, "P1")
    later = make(klass, room, D, "P2")
    html = client.get(f"/room/{session.pk}/").content.decode()
    assert f'data-next-url="/room/{later.pk}/"' in html
    assert 'aria-keyshortcuts="N"' in html


def test_room_view_offers_a_blank_plan_when_the_class_has_none(client, timetable, klass, room, pupils):
    Seat.objects.create(room=room, x=0, y=0)
    session = make(klass, room, D, "P1")
    html = client.get(f"/room/{session.pk}/").content.decode()
    assert "Start a blank plan" in html


def test_moved_room_fallback_from_the_room_view(client, timetable, klass, pupils):
    """A session moved to a room the class has no plan for: one tap seats them by zone and returns."""
    home = Room.objects.create(name="M2")
    home_front = Seat.objects.create(room=home, x=0, y=0, zone="front")
    home_plan = SeatingPlan.objects.create(klass=klass, room=home, active_from=D - datetime.timedelta(days=30))
    SeatAssignment.objects.create(seating_plan=home_plan, seat=home_front, pupil=pupils[0])

    hall = Room.objects.create(name="Hall")
    hall_front = Seat.objects.create(room=hall, x=0, y=0, zone="front")
    session = make(klass, hall, timezone.localdate(), "P1", Session.MOVED)

    html = client.get(f"/room/{session.pk}/").content.decode()
    assert "Seat by zone from M2" in html

    response = client.post("/plan/seating/new/", {"klass": klass.pk, "room": hall.pk, "next": f"/room/{session.pk}/"})
    assert response.url == f"/room/{session.pk}/"
    plan = SeatingPlan.current(klass, hall, session.date)
    assert plan.assignments.get().seat == hall_front

    html = client.get(f"/room/{session.pk}/").content.decode()
    assert "Aleya K" in html and "Seat by zone" not in html
