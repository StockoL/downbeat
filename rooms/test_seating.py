import datetime

import pytest

from rooms import seating
from rooms.models import Room, Seat, SeatAssignment, SeatingPlan

pytestmark = pytest.mark.django_db

TODAY = datetime.date(2026, 11, 2)


@pytest.fixture
def seats(room):
    return [Seat.objects.create(room=room, x=20 + i * 100, y=40, label=str(i + 1)) for i in range(4)]


@pytest.fixture
def plan(klass, room, seats):
    return SeatingPlan.objects.create(klass=klass, room=room, active_from=TODAY)


def seated(plan):
    return {a.seat.label: str(a.pupil) for a in plan.assignments.select_related("seat", "pupil")}


# --- Service ---

def test_move_into_empty_seat(plan, seats, pupils):
    seating.move(plan, pupils[0], seats[0])
    assert seated(plan) == {"1": "Aleya K"}


def test_move_onto_a_seated_pupil_swaps(plan, seats, pupils):
    seating.move(plan, pupils[0], seats[0])
    seating.move(plan, pupils[1], seats[1])
    seating.move(plan, pupils[0], seats[1])
    assert seated(plan) == {"1": "Jojo P", "2": "Aleya K"}


def test_unseated_pupil_dropped_on_a_seated_one_sends_them_back_to_the_list(plan, seats, pupils):
    seating.move(plan, pupils[0], seats[0])
    seating.move(plan, pupils[1], seats[0])
    assert seated(plan) == {"1": "Jojo P"}


def test_locked_seats_never_move(plan, seats, pupils):
    seating.move(plan, pupils[0], seats[0])
    seating.toggle_lock(plan, seats[0])
    with pytest.raises(seating.SeatLocked):
        seating.move(plan, pupils[1], seats[0])
    with pytest.raises(seating.SeatLocked):
        seating.move(plan, pupils[0], seats[1])
    with pytest.raises(seating.SeatLocked):
        seating.unseat(plan, pupils[0])
    assert seated(plan) == {"1": "Aleya K"}


def test_every_change_can_be_undone_in_reverse_order(plan, seats, pupils):
    snaps = []
    states = [seated(plan)]
    for action in [
        lambda: seating.move(plan, pupils[0], seats[0]),
        lambda: seating.move(plan, pupils[1], seats[1]),
        lambda: seating.move(plan, pupils[0], seats[1]),  # swap
        lambda: seating.move(plan, pupils[2], seats[0]),  # bumps Jojo to the list
        lambda: seating.toggle_lock(plan, seats[1]),
        lambda: seating.move(plan, pupils[1], seats[3]),
        lambda: seating.unseat(plan, pupils[2]),
    ]:
        snaps.append(action())
        states.append(seated(plan))
    for snap, expected in zip(reversed(snaps), reversed(states[:-1]), strict=True):
        seating.restore(plan, snap)
        assert seated(plan) == expected
    assert not plan.assignments.exists()


def test_undo_restores_the_lock(plan, seats, pupils):
    seating.move(plan, pupils[0], seats[0])
    snap = seating.toggle_lock(plan, seats[0])
    seating.restore(plan, snap)
    assert not plan.assignments.get().locked


def test_undo_stack_keeps_the_last_ten(plan):
    session = {}
    for i in range(12):
        seating.push_undo(session, plan, [[str(i), None, False]])
    assert seating.undo_count(session, plan) == 10
    assert seating.pop_undo(session, plan) == [["11", None, False]]


def test_current_plan_respects_active_dates(klass, room):
    old = SeatingPlan.objects.create(klass=klass, room=room, active_from=TODAY - datetime.timedelta(days=60), active_to=TODAY - datetime.timedelta(days=1))
    new = SeatingPlan.objects.create(klass=klass, room=room, active_from=TODAY)
    assert SeatingPlan.current(klass, room, TODAY) == new
    assert SeatingPlan.current(klass, room, TODAY - datetime.timedelta(days=5)) == old
    assert SeatingPlan.current(klass, room, TODAY - datetime.timedelta(days=90)) is None


# --- The no-plan-for-this-room fallback ---

def test_new_plan_without_a_plan_elsewhere_is_blank(klass, room, seats, pupils):
    plan, source = seating.create_plan(klass, room, TODAY)
    assert source is None
    assert plan.klass == klass and plan.room == room
    assert not plan.assignments.exists()


def test_new_plan_copies_pupils_by_zone_from_the_class_plan_elsewhere(klass, pupils):
    # Home room: teacher at the top; Aleya front, Jojo at a keyboard, Sam at the back.
    home = Room.objects.create(name="M2", teacher_x=400, teacher_y=0)
    front = Seat.objects.create(room=home, x=400, y=50, zone="front")
    keys = Seat.objects.create(room=home, x=100, y=300, zone="keyboard")
    back = Seat.objects.create(room=home, x=400, y=500, zone="back")
    home_plan = SeatingPlan.objects.create(klass=klass, room=home, active_from=TODAY)
    for seat, pupil in [(front, pupils[0]), (keys, pupils[1]), (back, pupils[2])]:
        SeatAssignment.objects.create(seating_plan=home_plan, seat=seat, pupil=pupil, locked=True)

    # Moved room: teacher at the bottom, so its front seats are low on the canvas. No keyboards.
    hall = Room.objects.create(name="Hall", teacher_x=400, teacher_y=600)
    hall_back = Seat.objects.create(room=hall, x=400, y=50, zone="back")
    hall_front_far = Seat.objects.create(room=hall, x=400, y=400, zone="front")
    hall_front_near = Seat.objects.create(room=hall, x=400, y=520, zone="front")

    plan, source = seating.create_plan(klass, hall, TODAY)

    assert source == home_plan
    placed = {a.pupil: a.seat for a in plan.assignments.all()}
    assert placed[pupils[0]] == hall_front_near  # front stays front, nearest the teacher first
    assert placed[pupils[2]] == hall_back
    assert pupils[1] not in placed  # no keyboard seat here: left to tidy at the desk
    assert hall_front_far not in placed.values()
    assert not any(a.locked for a in plan.assignments.all())
    assert home_plan.assignments.count() == 3  # the source is untouched


def test_new_plan_skips_pupils_who_have_left_the_class(klass, pupils, room, seats):
    home = Room.objects.create(name="M2")
    seat = Seat.objects.create(room=home, x=0, y=0)
    home_plan = SeatingPlan.objects.create(klass=klass, room=home, active_from=TODAY)
    SeatAssignment.objects.create(seating_plan=home_plan, seat=seat, pupil=pupils[0])
    klass.pupils.remove(pupils[0])
    plan, _ = seating.create_plan(klass, room, TODAY)
    assert not plan.assignments.exists()


# --- Views ---

def test_plan_pages_render(client, timetable, plan, pupils):
    assert client.get("/plan/").status_code == 200
    response = client.get(f"/plan/seating/{plan.pk}/")
    assert response.status_code == 200
    assert b"Aleya K" in response.content


def test_create_plan_view_redirects_to_editor(client, timetable, klass, room, seats):
    response = client.post("/plan/seating/new/", {"klass": klass.pk, "room": room.pk})
    plan = SeatingPlan.objects.get()
    assert response.url == f"/plan/seating/{plan.pk}/"


def test_create_plan_view_returns_to_a_safe_next(client, timetable, klass, room):
    response = client.post("/plan/seating/new/", {"klass": klass.pk, "room": room.pk, "next": "/room/abc/"})
    assert response.url == "/room/abc/"
    response = client.post("/plan/seating/new/", {"klass": klass.pk, "room": room.pk, "next": "https://example.com/"})
    assert response.url.startswith("/plan/seating/")


def test_move_view_and_undo_view(client, timetable, plan, seats, pupils):
    response = client.post(f"/plan/seating/{plan.pk}/move/", {"pupil": pupils[0].pk, "seat": seats[2].pk})
    assert response.status_code == 200 and b"Undo (1)" in response.content
    assert seated(plan) == {"3": "Aleya K"}
    client.post(f"/plan/seating/{plan.pk}/undo/")
    assert seated(plan) == {}


def test_move_to_bin_view(client, timetable, plan, seats, pupils):
    SeatAssignment.objects.create(seating_plan=plan, seat=seats[0], pupil=pupils[0])
    client.post(f"/plan/seating/{plan.pk}/move/", {"pupil": pupils[0].pk, "seat": "bin"})
    assert not plan.assignments.exists()


def test_move_view_refuses_a_locked_seat(client, timetable, plan, seats, pupils):
    SeatAssignment.objects.create(seating_plan=plan, seat=seats[0], pupil=pupils[0], locked=True)
    response = client.post(f"/plan/seating/{plan.pk}/move/", {"pupil": pupils[1].pk, "seat": seats[0].pk})
    assert response.status_code == 409
    assert seated(plan) == {"1": "Aleya K"}


def test_move_view_refuses_a_seat_from_another_room(client, timetable, plan, pupils):
    elsewhere = Seat.objects.create(room=Room.objects.create(name="Hall"))
    response = client.post(f"/plan/seating/{plan.pk}/move/", {"pupil": pupils[0].pk, "seat": elsewhere.pk})
    assert response.status_code == 404


def test_lock_view(client, timetable, plan, seats, pupils):
    SeatAssignment.objects.create(seating_plan=plan, seat=seats[0], pupil=pupils[0])
    client.post(f"/plan/seating/{plan.pk}/lock/", {"seat": seats[0].pk})
    assert plan.assignments.get().locked


def test_delete_plan_view(client, timetable, plan):
    client.post(f"/plan/seating/{plan.pk}/delete/")
    assert not SeatingPlan.objects.exists()


# --- Shuffle and duplicate ---

@pytest.fixture
def crowded(klass, pupils):
    """Six seats in a row and three keep-apart pairs among six pupils."""
    from pupils.models import Relationship
    from timetable.models import Pupil

    more = [Pupil.objects.create(first_name=n, surname_initial="Z") for n in ["Kai", "Mia", "Leo"]]
    klass.pupils.add(*more)
    everyone = [*pupils, *more]
    room = Room.objects.create(name="Row")
    seats = [Seat.objects.create(room=room, x=i * 100, y=0) for i in range(6)]
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=TODAY)
    for seat, pupil in zip(seats, everyone, strict=True):
        SeatAssignment.objects.create(seating_plan=plan, seat=seat, pupil=pupil)
    for a, b in [(0, 1), (2, 3), (4, 5)]:  # every pair starts side by side
        Relationship.objects.create(pupil_a=everyone[a], pupil_b=everyone[b], kind="keep_apart")
    return plan, seats, everyone


def keep_apart_neighbours(plan):
    from rooms.solver import violations
    return violations(seating.build_problem(plan), {a.seat_id: a.pupil_id for a in plan.assignments.all()})


def test_shuffle_separates_every_keep_apart_pair(client, timetable, crowded):
    plan, _, _ = crowded
    assert len(keep_apart_neighbours(plan)) == 3
    response = client.post(f"/plan/seating/{plan.pk}/shuffle/")
    assert response.status_code == 200 and b"Shuffled" in response.content
    assert keep_apart_neighbours(plan) == []
    assert plan.assignments.count() == 6


def test_shuffle_never_moves_a_locked_seat(client, timetable, crowded):
    plan, seats, everyone = crowded
    plan.assignments.filter(seat=seats[5]).update(locked=True)
    for _ in range(5):
        client.post(f"/plan/seating/{plan.pk}/shuffle/")
        assert plan.assignments.get(seat=seats[5]).pupil == everyone[5]


def test_one_undo_puts_the_whole_shuffle_back(client, timetable, crowded):
    plan, _, _ = crowded
    before = seated(plan)
    client.post(f"/plan/seating/{plan.pk}/shuffle/")
    client.post(f"/plan/seating/{plan.pk}/undo/")
    assert seated(plan) == before


def test_shuffle_refuses_rather_than_break_a_keep_apart(client, timetable, crowded):
    plan, seats, _ = crowded
    plan.assignments.filter(seat__in=seats[:2]).update(locked=True)  # a keep-apart pair locked side by side
    before = seated(plan)
    response = client.post(f"/plan/seating/{plan.pk}/shuffle/")
    assert response.status_code == 409 and b"Couldn" in response.content
    assert seated(plan) == before


def test_duplicate_keeps_the_old_plan_as_history(client, timetable, crowded):
    plan, _, _ = crowded
    SeatingPlan.objects.filter(pk=plan.pk).update(active_from=TODAY - datetime.timedelta(days=40))
    plan.refresh_from_db()
    response = client.post(f"/plan/seating/{plan.pk}/duplicate/")
    copy = SeatingPlan.objects.exclude(pk=plan.pk).get()
    assert response.url == f"/plan/seating/{copy.pk}/"
    plan.refresh_from_db()
    from django.utils import timezone
    today = timezone.localdate()
    assert plan.active_to == today - datetime.timedelta(days=1) and copy.active_from == today
    assert seated(copy) == seated(plan)
    assert SeatingPlan.current(plan.klass, plan.room, today) == copy
    assert SeatingPlan.current(plan.klass, plan.room, today - datetime.timedelta(days=1)) == plan
