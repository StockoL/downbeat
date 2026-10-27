"""
Cross-cutting checks: every mutating endpoint refuses GET, the error paths answer cleanly,
and seating invariants hold under long random sequences of moves.
"""

import datetime
import random
import uuid

import pytest
from django.urls import reverse

from notes.models import Note, SpokenTo
from rooms import seating
from rooms.models import Room, Seat, SeatingPlan
from timetable.models import Pupil, Session, SessionAttendance

pytestmark = pytest.mark.django_db

ANY = uuid.uuid4()

POST_ONLY = [
    ("slot_delete", [ANY]), ("class_remove_pupil", [ANY, ANY]), ("class_delete", [ANY]),
    ("pupil_delete", [ANY]), ("session_generate", []), ("session_delete", [ANY]),
    ("room_delete", [ANY]), ("seats_add", [ANY]), ("seat_update", [ANY]), ("seat_delete", [ANY]),
    ("teacher_move", [ANY]),
    ("seating_create", []), ("seating_move", [ANY]), ("seating_lock", [ANY]), ("seating_undo", [ANY]),
    ("seating_delete", [ANY]),
    ("note_add", [ANY]), ("note_remove", [ANY]), ("note_undo", [ANY]), ("action_done", [ANY]),
    ("spoken_toggle", [ANY]), ("absent_toggle", [ANY]), ("pick", [ANY]),
]


@pytest.mark.parametrize("name,args", POST_ONLY)
def test_mutating_endpoints_refuse_get(client, timetable, name, args):
    assert client.get(reverse(name, args=args)).status_code == 405


@pytest.mark.parametrize("name,args", POST_ONLY)
def test_mutating_endpoints_404_on_unknown_rows(client, timetable, name, args):
    if not args:
        pytest.skip("takes its rows from the form")
    assert client.post(reverse(name, args=args), {"pupil": ANY, "seat": ANY, "session": ANY}).status_code == 404


D = datetime.date(2026, 11, 2)


@pytest.fixture
def seat(room):
    return Seat.objects.create(room=room, x=10, y=10)


@pytest.fixture
def lesson(timetable, klass, room, pupils):
    return Session.objects.create(date=D, period="P1", klass=klass, room=room)


# --- Rooms ---

def test_edit_room_saves(client, timetable, room):
    client.post(f"/settings/rooms/{room.pk}/", {"name": "Music 2", "canvas_width": "1200", "canvas_height": "800"})
    room.refresh_from_db()
    assert (room.name, room.canvas_width, room.canvas_height) == ("Music 2", 1200, 800)


def test_seat_update_rejects_non_numbers(client, timetable, seat):
    assert client.post(f"/settings/rooms/seats/{seat.pk}/", {"x": "left"}).status_code == 400
    seat.refresh_from_db()
    assert seat.x == 10


def test_teacher_move_needs_both_coordinates(client, timetable, room):
    assert client.post(f"/settings/rooms/{room.pk}/teacher/", {"x": "10"}).status_code == 400
    room.refresh_from_db()
    assert room.teacher_x is None


# --- Room view ---

def test_note_add_with_an_unknown_type_records_nothing(client, lesson, pupils):
    response = client.post(f"/room/{lesson.pk}/notes/", {"pupil": pupils[0].pk, "note_type": ANY})
    assert response.status_code == 404
    assert not Note.objects.exists()


def test_pick_with_everyone_absent_says_so_and_records_nothing(client, lesson, pupils):
    for pupil in pupils:
        SessionAttendance.objects.create(session=lesson, pupil=pupil, present=False)
    html = client.post(f"/room/{lesson.pk}/pick/").content.decode()
    assert "No one to pick" in html
    assert not SpokenTo.objects.exists()


def test_undo_with_an_empty_stack_changes_nothing(client, lesson):
    assert client.post(f"/room/{lesson.pk}/notes/undo/").status_code == 200


# --- Seating invariants under random sequences ---

@pytest.mark.parametrize("seed", range(25))
def test_random_moves_keep_locked_seats_still_and_one_seat_per_pupil(klass, seed):
    rng = random.Random(seed)
    room = Room.objects.create(name=f"R{seed}")
    seats = [Seat.objects.create(room=room, x=i * 90, y=0) for i in range(8)]
    pupils = [Pupil.objects.create(first_name=f"P{i}", surname_initial="X") for i in range(10)]
    klass.pupils.add(*pupils)
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=D)

    stack = []
    for _ in range(60):
        locked_before = {a.seat_id: a.pupil_id for a in plan.assignments.filter(locked=True)}
        action = rng.choice(["move", "move", "move", "unseat", "lock", "undo"])
        try:
            if action == "move":
                snap = seating.move(plan, rng.choice(pupils), rng.choice(seats))
            elif action == "unseat":
                snap = seating.unseat(plan, rng.choice(pupils))
            elif action == "lock":
                snap = seating.toggle_lock(plan, rng.choice(seats))
            else:
                snap = None
                if stack:
                    seating.restore(plan, stack.pop())
        except seating.SeatLocked:
            snap = None
        if snap:
            stack.append(snap)

        rows = list(plan.assignments.all())
        assert len({a.seat_id for a in rows}) == len(rows), "two pupils in one seat"
        assert len({a.pupil_id for a in rows}) == len(rows), "one pupil in two seats"
        if action in ("move", "unseat"):
            locked_after = {a.seat_id: a.pupil_id for a in rows if a.locked}
            assert locked_after == locked_before, "a locked seat moved"


# --- Double taps ---

def test_every_htmx_post_disables_its_control_while_in_flight():
    """A double tap in the room must never record twice."""
    import re
    from pathlib import Path

    from django.conf import settings

    unguarded = []
    for path in Path(settings.BASE_DIR, "templates").rglob("*.html"):
        for tag in re.findall(r"<(?:button|form)\b[^>]*\bhx-post=[^>]*>", path.read_text(encoding="utf-8")):
            if "hx-disabled-elt=" not in tag:
                unguarded.append(f"{path.name}: {tag[:80]}")
    assert not unguarded, unguarded
