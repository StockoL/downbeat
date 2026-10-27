import datetime
import random

import pytest

from notes import services
from notes.models import SpokenTo
from rooms.models import Seat, SeatAssignment, SeatingPlan
from timetable.models import Class, Session, SessionAttendance

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 11, 2)


@pytest.fixture
def lesson(timetable, klass, room, pupils):
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=D)
    for i, pupil in enumerate(pupils):
        SeatAssignment.objects.create(seating_plan=plan, seat=Seat.objects.create(room=room, x=i * 100, y=0), pupil=pupil)
    return Session.objects.create(date=D, period="P1", klass=klass, room=room)


@pytest.fixture
def next_lesson(lesson):
    return Session.objects.create(date=D + datetime.timedelta(days=2), period="P2", klass=lesson.klass, room=lesson.room)


def marks(html, pupil):
    """The opening tag of a pupil's seat marks."""
    start = html.index(f'id="marks-{pupil.pk}"')
    return html[start:html.index(">", start)]


# --- Spoken to ---

def test_spoken_to_toggle_records_and_closes_the_sheet(client, lesson, pupils):
    response = client.post(f"/room/{lesson.pk}/spoken/", {"pupil": pupils[0].pk})
    assert response["HX-Trigger"] == "closeSheet"
    assert SpokenTo.objects.filter(session=lesson, pupil=pupils[0]).count() == 1
    assert "data-spoken" in marks(response.content.decode(), pupils[0])


def test_spoken_to_toggle_a_second_time_takes_it_back(client, lesson, pupils):
    client.post(f"/room/{lesson.pk}/spoken/", {"pupil": pupils[0].pk})
    client.post(f"/room/{lesson.pk}/spoken/", {"pupil": pupils[0].pk})
    assert not SpokenTo.objects.exists()


def test_seat_dims_in_the_room_view_when_spoken_to(client, lesson, pupils):
    SpokenTo.objects.create(session=lesson, pupil=pupils[1])
    html = client.get(f"/room/{lesson.pk}/").content.decode()
    assert "data-spoken" in marks(html, pupils[1])
    assert "data-spoken" not in marks(html, pupils[0])


def test_next_session_highlights_who_was_missed_last_time(client, lesson, next_lesson, pupils):
    SpokenTo.objects.create(session=lesson, pupil=pupils[0])
    html = client.get(f"/room/{next_lesson.pk}/").content.decode()
    assert "data-missed" not in marks(html, pupils[0])
    assert "data-missed" in marks(html, pupils[1]) and "data-missed" in marks(html, pupils[2])


def test_no_highlights_when_spoken_to_went_unused_last_time(client, lesson, next_lesson, pupils):
    html = client.get(f"/room/{next_lesson.pk}/").content.decode()
    assert "data-missed" not in html


def test_highlights_come_from_the_same_class_only(client, lesson, next_lesson, pupils, room):
    other = Session.objects.create(date=D + datetime.timedelta(days=1), period="P1", klass=Class.objects.create(name="9Y"), room=room)
    SpokenTo.objects.create(session=lesson, pupil=pupils[0])
    SpokenTo.objects.create(session=other, pupil=pupils[1])  # 9Y's lesson in between doesn't count
    html = client.get(f"/room/{next_lesson.pk}/").content.decode()
    assert "data-missed" in marks(html, pupils[1])


# --- Absence ---

def test_absent_toggle(client, lesson, pupils):
    response = client.post(f"/room/{lesson.pk}/absent/", {"pupil": pupils[2].pk})
    assert response["HX-Trigger"] == "closeSheet"
    assert not SessionAttendance.objects.get(session=lesson, pupil=pupils[2]).present
    assert "data-absent" in marks(response.content.decode(), pupils[2])
    client.post(f"/room/{lesson.pk}/absent/", {"pupil": pupils[2].pk})
    assert SessionAttendance.objects.get(session=lesson, pupil=pupils[2]).present


# --- Picker ---

def test_picker_draws_from_not_yet_spoken_to_and_skips_absentees(lesson, pupils):
    SpokenTo.objects.create(session=lesson, pupil=pupils[0])
    SessionAttendance.objects.create(session=lesson, pupil=pupils[1], present=False)
    for seed in range(20):
        SpokenTo.objects.filter(session=lesson, pupil=pupils[2]).delete()
        assert services.draw(lesson, rng=random.Random(seed)) == pupils[2]


def test_picker_avoids_repeats_until_everyone_has_had_a_turn(lesson, pupils):
    rng = random.Random(1)
    first_round = [services.draw(lesson, rng=rng) for _ in pupils]
    assert set(first_round) == set(pupils)
    assert services.draw(lesson, rng=rng) in pupils  # then the whole class again
    assert SpokenTo.objects.filter(session=lesson).count() == 4


def test_picker_whole_class_can_repeat_but_never_draws_the_absent(lesson, pupils):
    SpokenTo.objects.create(session=lesson, pupil=pupils[0])
    SessionAttendance.objects.create(session=lesson, pupil=pupils[2], present=False)
    drawn = {services.draw(lesson, whole_class=True, rng=random.Random(seed)) for seed in range(30)}
    assert drawn == {pupils[0], pupils[1]}


def test_picker_with_everyone_absent_draws_no_one(lesson, pupils):
    for pupil in pupils:
        SessionAttendance.objects.create(session=lesson, pupil=pupil, present=False)
    assert services.draw(lesson) is None
    assert not SpokenTo.objects.exists()


def test_pick_view_records_spoken_to_and_shows_one_name(client, lesson, pupils):
    response = client.post(f"/room/{lesson.pk}/pick/")
    row = SpokenTo.objects.get()
    html = response.content.decode()
    assert 'class="picker__name"' in html.split('hx-swap-oob')[0]  # the picker is the main content
    assert str(row.pupil) in html
    assert "data-spoken" in marks(html, row.pupil)


def test_pick_absent_takes_back_the_draw_marks_absent_and_draws_again(client, lesson, pupils):
    client.post(f"/room/{lesson.pk}/pick/")
    first = SpokenTo.objects.get().pupil
    client.post(f"/room/{lesson.pk}/pick/", {"absent": first.pk})
    assert not SessionAttendance.objects.get(session=lesson, pupil=first).present
    assert not SpokenTo.objects.filter(pupil=first).exists()
    assert SpokenTo.objects.count() == 1 and SpokenTo.objects.get().pupil != first


def test_sheet_shows_toggle_states(client, lesson, pupils):
    SpokenTo.objects.create(session=lesson, pupil=pupils[0])
    html = client.get(f"/room/{lesson.pk}/sheet/{pupils[0].pk}/").content.decode()
    assert 'aria-pressed="true"' in html.split("Spoken to")[0]
