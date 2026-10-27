import datetime

import pytest

from notes.models import Note, NoteType
from rooms.models import Seat, SeatAssignment, SeatingPlan
from timetable.models import Session

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 11, 2)


@pytest.fixture
def types(db):
    return {
        "hp": NoteType.objects.create(label="House point", icon="★", is_house_point=True, order=3),
        "chase": NoteType.objects.create(label="Chase homework", icon="!", is_actionable_default=True, order=0),
    }


@pytest.fixture
def lesson(timetable, klass, room, pupils):
    """A P1 session with the class seated."""
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=D)
    for i, pupil in enumerate(pupils):
        SeatAssignment.objects.create(seating_plan=plan, seat=Seat.objects.create(room=room, x=i * 100, y=0), pupil=pupil)
    return Session.objects.create(date=D, period="P1", klass=klass, room=room)


def add(client, session, pupil, **data):
    return client.post(f"/room/{session.pk}/notes/", {"pupil": pupil.pk, **data})


# --- Note sheet ---

def test_sheet_lists_types_house_point_first_then_free_text_last(client, lesson, pupils, types):
    html = client.get(f"/room/{lesson.pk}/sheet/{pupils[0].pk}/").content.decode()
    assert html.index("House point") < html.index("Chase homework") < html.index("Free text")
    assert "<textarea" not in html  # no field until free text is chosen


def test_free_text_is_the_only_button_that_opens_a_field(client, lesson, pupils, types):
    html = client.get(f"/room/{lesson.pk}/sheet/{pupils[0].pk}/?free").content.decode()
    assert "<textarea" in html


def test_one_tap_records_a_note_and_closes_the_sheet(client, lesson, pupils, types):
    response = add(client, lesson, pupils[0], note_type=types["hp"].pk)
    assert response["HX-Trigger"] == "closeSheet"
    note = Note.objects.get()
    assert (note.session, note.pupil, note.note_type, note.actionable) == (lesson, pupils[0], types["hp"], False)
    html = response.content.decode()
    assert 'id="log-panel"' in html and "House point" in html  # the log
    assert f'id="marks-{pupils[0].pk}"' in html and "★" in html  # the seat badge


def test_actionable_type_makes_an_actionable_note(client, lesson, pupils, types):
    response = add(client, lesson, pupils[1], note_type=types["chase"].pk)
    assert Note.objects.get().actionable
    assert 'id="actions-button"' in response.content.decode()


def test_free_text_note(client, lesson, pupils, types):
    add(client, lesson, pupils[0], text="  Bring a capo  ", actionable="on")
    note = Note.objects.get()
    assert note.note_type is None and note.text == "Bring a capo" and note.actionable


def test_empty_free_text_records_nothing(client, lesson, pupils):
    add(client, lesson, pupils[0], text="   ")
    assert not Note.objects.exists()


def test_room_view_shows_badges_log_and_unread(client, lesson, pupils, types):
    add(client, lesson, pupils[0], note_type=types["hp"].pk)
    add(client, lesson, pupils[1], note_type=types["chase"].pk)
    html = client.get(f"/room/{lesson.pk}/").content.decode()
    assert "★" in html and "Chase homework" in html
    assert 'aria-label="1 open"' in html


def test_room_view_with_no_notes_has_no_nags(client, lesson, types):
    html = client.get(f"/room/{lesson.pk}/").content.decode()
    assert 'aria-label="0 open"' not in html
    assert 'class="room-bar__count"' not in html
    assert 'data-status="danger"' not in html and 'data-status="warning"' not in html


# --- Remove and undo ---

def test_remove_note_goes_to_the_bin(client, lesson, pupils, types):
    add(client, lesson, pupils[0], note_type=types["hp"].pk)
    note = Note.objects.get()
    client.post(f"/room/notes/{note.pk}/remove/")
    note.refresh_from_db()
    assert note.deleted_at is not None
    assert "House point" not in client.get(f"/room/{lesson.pk}/").content.decode().split('id="log-panel"')[1]


def test_undo_reverses_adds_and_removes_in_order(client, lesson, pupils, types):
    add(client, lesson, pupils[0], note_type=types["hp"].pk)
    add(client, lesson, pupils[1], note_type=types["hp"].pk)
    first, _second = Note.objects.all()
    client.post(f"/room/notes/{first.pk}/remove/")
    assert Note.objects.live().count() == 1

    client.post(f"/room/{lesson.pk}/notes/undo/")  # restores the removed note
    assert Note.objects.live().count() == 2
    client.post(f"/room/{lesson.pk}/notes/undo/")  # takes back the second add
    assert list(Note.objects.live()) == [first]
    client.post(f"/room/{lesson.pk}/notes/undo/")
    client.post(f"/room/{lesson.pk}/notes/undo/")  # nothing left to undo
    assert not Note.objects.live().exists()


# --- Inbox and actions ---

def test_inbox_lists_a_pupils_notes_newest_first(client, lesson, pupils, types):
    add(client, lesson, pupils[0], note_type=types["hp"].pk)
    add(client, lesson, pupils[0], text="Lovely phrasing")
    html = client.get(f"/room/{lesson.pk}/inbox/{pupils[0].pk}/").content.decode()
    assert html.index("Lovely phrasing") < html.index("House point")


def test_actions_carry_to_the_next_session_with_the_class(client, timetable, lesson, pupils, types):
    add(client, lesson, pupils[1], note_type=types["chase"].pk)
    add(client, lesson, pupils[0], note_type=types["hp"].pk)  # not actionable
    later = Session.objects.create(date=D + datetime.timedelta(days=2), period="P2", klass=lesson.klass, room=lesson.room)

    html = client.get(f"/room/{later.pk}/actions/").content.decode()
    assert "Chase homework" in html and "House point" not in html
    note = Note.objects.get(note_type=types["chase"])
    assert note.carried_to_session == later


def test_actions_do_not_leak_backwards_or_to_other_classes(client, timetable, lesson, pupils, types, room):
    from timetable.models import Class
    later = Session.objects.create(date=D, period="P2", klass=lesson.klass, room=room)
    other = Session.objects.create(date=D, period="P2", klass=Class.objects.create(name="9Y"), room=room)
    add(client, later, pupils[1], note_type=types["chase"].pk)
    assert "Chase homework" not in client.get(f"/room/{lesson.pk}/actions/").content.decode()
    assert "Chase homework" not in client.get(f"/room/{other.pk}/actions/").content.decode()


def test_marking_an_action_done(client, lesson, pupils, types):
    add(client, lesson, pupils[1], note_type=types["chase"].pk)
    note = Note.objects.get()
    response = client.post(f"/room/notes/{note.pk}/done/", {"session": lesson.pk})
    note.refresh_from_db()
    assert note.done_at is not None
    html = response.content.decode()
    assert 'id="sheet-body" hx-swap-oob="innerHTML"' in html and "Nothing open." in html


# --- Settings ---

def test_note_types_settings_save_and_add(client, timetable, types):
    hp, chase = types["hp"], types["chase"]
    data = {
        "form-TOTAL_FORMS": "3", "form-INITIAL_FORMS": "2", "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
        "form-0-id": chase.pk, "form-0-order": "0", "form-0-label": "Chase", "form-0-icon": "!", "form-0-is_actionable_default": "on",
        "form-1-id": hp.pk, "form-1-order": "1", "form-1-label": "House point", "form-1-icon": "★", "form-1-is_house_point": "on",
        "form-2-order": "2", "form-2-label": "Kit", "form-2-icon": "🎧",
    }
    client.post("/settings/note-types/", data)
    assert sorted(NoteType.objects.values_list("label", flat=True)) == ["Chase", "House point", "Kit"]


def test_a_used_note_type_cannot_be_deleted(client, lesson, pupils, types):
    add(client, lesson, pupils[0], note_type=types["hp"].pk)
    hp, chase = types["hp"], types["chase"]
    data = {
        "form-TOTAL_FORMS": "2", "form-INITIAL_FORMS": "2", "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
        "form-0-id": chase.pk, "form-0-order": "0", "form-0-label": "Chase homework",
        "form-1-id": hp.pk, "form-1-order": "3", "form-1-label": "House point", "form-1-DELETE": "on",
    }
    client.post("/settings/note-types/", data)
    assert NoteType.objects.filter(pk=hp.pk).exists()


def test_a_session_with_notes_cannot_be_deleted(client, lesson, pupils, types):
    add(client, lesson, pupils[0], note_type=types["hp"].pk)
    client.post(f"/settings/sessions/{lesson.pk}/delete/")
    assert Session.objects.filter(pk=lesson.pk).exists()
