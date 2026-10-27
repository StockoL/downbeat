import datetime

import pytest
from reportlab import rl_config

from pupils.models import FlagType, PupilFlag, Relationship
from rooms.models import Seat, SeatAssignment, SeatingPlan
from timetable.models import Session

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 11, 2)
LABEL = "Private worry"


@pytest.fixture
def flag(db):
    return FlagType.objects.create(label=LABEL, colour=3, placement_rule="near_teacher", what_works="Front, early warning")


@pytest.fixture
def flagged(pupils, flag):
    PupilFlag.objects.create(pupil=pupils[0], flag_type=flag, note="From the SENCo")
    return pupils[0]


@pytest.fixture
def lesson(timetable, klass, room, pupils):
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=D)
    for i, pupil in enumerate(pupils[:2]):
        SeatAssignment.objects.create(seating_plan=plan, seat=Seat.objects.create(room=room, x=i * 100, y=0), pupil=pupil)
    return Session.objects.create(date=D, period="P1", klass=klass, room=room)


# --- Settings → Flags ---

def formset(*rows, initial=0):
    data = {"form-TOTAL_FORMS": str(len(rows)), "form-INITIAL_FORMS": str(initial), "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000"}
    for i, row in enumerate(rows):
        data.update({f"form-{i}-{k}": v for k, v in row.items()})
    return data


def test_flag_types_page_renders(client, timetable, flag):
    html = client.get("/settings/flags/").content.decode()
    assert LABEL in html and 'class="flag-swatch flag-8"' in html


def test_add_a_flag_type(client, timetable):
    client.post("/settings/flags/", formset({"colour": "5", "label": "Hearing", "category": "adjustment", "placement_rule": "front"}))
    assert FlagType.objects.get().colour == 5


def test_two_flags_cannot_share_a_colour(client, timetable, flag):
    client.post("/settings/flags/", formset(
        {"id": flag.pk, "colour": "3", "label": LABEL, "category": "other", "placement_rule": "none"},
        {"colour": "3", "label": "Another", "category": "other", "placement_rule": "none"}, initial=1))
    assert FlagType.objects.count() == 1


def test_a_flag_in_use_cannot_be_deleted(client, timetable, flagged, flag):
    client.post("/settings/flags/", formset(
        {"id": flag.pk, "colour": "3", "label": LABEL, "category": "other", "placement_rule": "none", "DELETE": "on"}, initial=1))
    assert FlagType.objects.exists()


# --- The pupil page ---

def test_pupil_page_shows_the_label_note_and_what_works(client, timetable, flagged):
    html = client.get(f"/pupils/{flagged.pk}/").content.decode()
    assert LABEL in html and "From the SENCo" in html and "Front, early warning" in html


def test_add_and_remove_a_pupil_flag(client, timetable, pupils, flag):
    client.post(f"/pupils/{pupils[1].pk}/", {"add_flag": "", "flag_type": flag.pk, "since": "2026-09-01", "note": ""})
    pupil_flag = PupilFlag.objects.get(pupil=pupils[1])
    assert pupil_flag.since == datetime.date(2026, 9, 1)
    client.post(f"/pupils/flags/{pupil_flag.pk}/remove/")
    assert not PupilFlag.objects.exists()


def test_the_same_flag_cannot_be_added_twice(client, timetable, flagged, flag):
    client.post(f"/pupils/{flagged.pk}/", {"add_flag": "", "flag_type": flag.pk})
    assert PupilFlag.objects.count() == 1


def test_pupils_area_pages_render(client, timetable, klass, flagged):
    assert client.get("/pupils/").status_code == 200
    html = client.get(f"/pupils/class/{klass.pk}/").content.decode()
    assert "flag-swatch flag-3" in html
    assert LABEL not in html  # the class list shows colour only


# --- Colour only, everywhere else ---

def test_room_view_seat_shows_the_flag_as_colour_only(client, lesson, flagged):
    html = client.get(f"/room/{lesson.pk}/").content.decode()
    assert '<span class="seat__flags" aria-hidden="true"><i class="flag-3"></i></span>' in html
    assert LABEL not in html and "From the SENCo" not in html


def test_seating_editor_shows_the_flag_as_colour_only(client, lesson, flagged):
    plan = SeatingPlan.objects.get()
    html = client.get(f"/plan/seating/{plan.pk}/").content.decode()
    assert 'class="flag-3"' in html and LABEL not in html


def test_projector_and_cover_show_no_flags(client, lesson, flagged, monkeypatch):
    html = client.get(f"/room/{lesson.pk}/projector/").content.decode()
    assert "seat__flags" not in html and "flag-" not in html and LABEL not in html
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    assert LABEL.encode() not in client.get(f"/room/{lesson.pk}/cover.pdf").content


def test_lesson_state_never_carries_flag_labels(client, lesson, flagged):
    assert LABEL not in client.get(f"/room/{lesson.pk}/state/").content.decode()


# --- Relationships ---

def test_relationships_are_stored_once_whichever_side_adds_them(client, timetable, pupils):
    client.post(f"/pupils/{pupils[1].pk}/", {"add_relationship": "", "other": pupils[0].pk, "kind": "keep_apart", "source": "HoY"})
    rel = Relationship.objects.get()
    assert str(rel.pupil_a_id) < str(rel.pupil_b_id)
    assert {rel.pupil_a, rel.pupil_b} == {pupils[0], pupils[1]}
    # shown on both pages, and the partner can't be chosen again from either side
    for pupil, other in [(pupils[0], pupils[1]), (pupils[1], pupils[0])]:
        html = client.get(f"/pupils/{pupil.pk}/").content.decode()
        assert "Keep apart" in html and str(other) in html
    client.post(f"/pupils/{pupils[0].pk}/", {"add_relationship": "", "other": pupils[1].pk, "kind": "pair_well"})
    assert Relationship.objects.count() == 1


def test_relationships_are_only_offered_with_classmates(client, timetable, pupils):
    from timetable.models import Pupil
    stranger = Pupil.objects.create(first_name="Zed", surname_initial="Q")
    client.post(f"/pupils/{pupils[0].pk}/", {"add_relationship": "", "other": stranger.pk, "kind": "keep_apart"})
    assert not Relationship.objects.exists()


def test_remove_a_relationship(client, timetable, pupils):
    rel = Relationship.objects.create(pupil_a=pupils[0], pupil_b=pupils[1], kind="pair_well")
    client.post(f"/pupils/{pupils[0].pk}/relationships/{rel.pk}/remove/")
    assert not Relationship.objects.exists()


# --- Seating editor validation ---

@pytest.fixture
def row(timetable, klass, room, pupils):
    """Three seats in a row (neighbours 100 apart) and one far away; pupils 0 and 1 side by side."""
    seats = [Seat.objects.create(room=room, x=x, y=y, zone=zone) for x, y, zone in [(0, 0, "front"), (100, 0, ""), (200, 0, ""), (700, 500, "back")]]
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=D)
    SeatAssignment.objects.create(seating_plan=plan, seat=seats[0], pupil=pupils[0])
    SeatAssignment.objects.create(seating_plan=plan, seat=seats[1], pupil=pupils[1])
    SeatAssignment.objects.create(seating_plan=plan, seat=seats[3], pupil=pupils[2])
    return plan


def test_editor_draws_a_line_between_keep_apart_neighbours(client, row, pupils):
    Relationship.objects.create(pupil_a=pupils[0], pupil_b=pupils[1], kind="keep_apart")
    Relationship.objects.create(pupil_a=pupils[0], pupil_b=pupils[2], kind="keep_apart")  # far apart: fine
    html = client.get(f"/plan/seating/{row.pk}/").content.decode()
    assert html.count('data-kind="keep_apart"') == 1
    assert "1 keep-apart pair side by side." in html


def test_editor_marks_pair_well_neighbours_quietly(client, row, pupils):
    Relationship.objects.create(pupil_a=pupils[0], pupil_b=pupils[1], kind="pair_well")
    html = client.get(f"/plan/seating/{row.pk}/").content.decode()
    assert 'data-kind="pair_well"' in html and "side by side" not in html


def test_editor_outlines_a_seat_that_breaks_a_flag_rule(client, row, pupils):
    front = FlagType.objects.create(label="Front", colour=2, placement_rule="front")
    PupilFlag.objects.create(pupil=pupils[0], flag_type=front)  # in the front seat: met
    PupilFlag.objects.create(pupil=pupils[2], flag_type=front)  # at the back: not met
    html = client.get(f"/plan/seating/{row.pk}/").content.decode()
    assert html.count("data-rule-unmet") == 1
    assert "1 seat not meeting a flag's seating rule." in html


def test_a_move_redraws_the_checks(client, row, pupils):
    Relationship.objects.create(pupil_a=pupils[0], pupil_b=pupils[1], kind="keep_apart")
    far = Seat.objects.get(x=200)
    html = client.post(f"/plan/seating/{row.pk}/move/", {"pupil": pupils[1].pk, "seat": far.pk}).content.decode()
    assert 'data-kind="keep_apart"' not in html
