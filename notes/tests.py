import datetime
import json
import uuid

import pytest
from django.utils import timezone

from notes.models import Note, NoteType, SpokenTo
from notes.state import lesson_state
from rooms.models import Seat, SeatAssignment, SeatingPlan
from timetable.models import Class, Session, SessionAttendance

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
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=D)
    for i, pupil in enumerate(pupils[:2]):
        SeatAssignment.objects.create(seating_plan=plan, seat=Seat.objects.create(room=room, x=i * 100, y=0), pupil=pupil)
    return Session.objects.create(date=D, period="P1", klass=klass, room=room)


def at(minutes=0):
    return (timezone.now() - datetime.timedelta(minutes=30) + datetime.timedelta(minutes=minutes)).isoformat()


def op(kind, **fields):
    return {"op_id": str(uuid.uuid4()), "type": kind, "at": fields.pop("at", at()), **fields}


def sync(client, *ops):
    response = client.post("/sync/", json.dumps({"ops": list(ops)}), content_type="application/json")
    assert response.status_code == 200, response.content
    return response.json()


# --- Notes ---

def test_note_add_records_the_note_at_the_time_it_was_caught(client, lesson, pupils, types):
    note_id, caught = str(uuid.uuid4()), at(5)
    result = sync(client, op("note.add", id=note_id, session=str(lesson.pk), pupil=str(pupils[0].pk), note_type=str(types["hp"].pk), at=caught))
    assert len(result["applied"]) == 1 and not result["rejected"]
    note = Note.objects.get(pk=note_id)
    assert (note.session, note.pupil, note.note_type, note.actionable) == (lesson, pupils[0], types["hp"], False)
    assert note.created_at.isoformat() == caught


def test_note_type_decides_actionable_not_the_device(client, lesson, pupils, types):
    note_id = str(uuid.uuid4())
    sync(client, op("note.add", id=note_id, session=str(lesson.pk), pupil=str(pupils[0].pk), note_type=str(types["chase"].pk), actionable=False))
    assert Note.objects.get(pk=note_id).actionable


def test_free_text_note(client, lesson, pupils):
    note_id = str(uuid.uuid4())
    sync(client, op("note.add", id=note_id, session=str(lesson.pk), pupil=str(pupils[0].pk), note_type=None, text=" Brought a capo ", actionable=True))
    note = Note.objects.get(pk=note_id)
    assert note.note_type is None and note.text == "Brought a capo" and note.actionable


def test_sending_the_same_queue_twice_changes_nothing(client, lesson, pupils, types):
    note_id, spoken_id = str(uuid.uuid4()), str(uuid.uuid4())
    ops = [
        op("note.add", id=note_id, session=str(lesson.pk), pupil=str(pupils[0].pk), note_type=str(types["hp"].pk)),
        op("spoken.add", id=spoken_id, session=str(lesson.pk), pupil=str(pupils[1].pk)),
    ]
    first, again = sync(client, *ops), sync(client, *ops)
    assert first["applied"] == again["applied"] == [o["op_id"] for o in ops]
    assert Note.objects.count() == 1 and SpokenTo.objects.count() == 1


def test_remove_restore_and_last_write_wins(client, lesson, pupils, types):
    note_id = str(uuid.uuid4())
    sync(client, op("note.add", id=note_id, session=str(lesson.pk), pupil=str(pupils[0].pk), note_type=str(types["hp"].pk), at=at(0)))
    sync(client, op("note.remove", note=note_id, at=at(2)))
    assert Note.objects.get(pk=note_id).deleted_at is not None
    sync(client, op("note.restore", note=note_id, at=at(1)))  # older than the removal: ignored
    assert Note.objects.get(pk=note_id).deleted_at is not None
    sync(client, op("note.restore", note=note_id, at=at(3)))
    assert Note.objects.get(pk=note_id).deleted_at is None


def test_action_done(client, lesson, pupils, types):
    note_id = str(uuid.uuid4())
    sync(client,
         op("note.add", id=note_id, session=str(lesson.pk), pupil=str(pupils[0].pk), note_type=str(types["chase"].pk), at=at(0)),
         op("action.done", note=note_id, at=at(1)))
    assert Note.objects.get(pk=note_id).done_at is not None


# --- Spoken to and attendance ---

def test_spoken_add_remove_and_clear(client, lesson, pupils):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    sync(client,
         op("spoken.add", id=a, session=str(lesson.pk), pupil=str(pupils[0].pk), at=at(0)),
         op("spoken.add", id=b, session=str(lesson.pk), pupil=str(pupils[0].pk), at=at(1)))
    assert SpokenTo.objects.count() == 2
    sync(client, op("spoken.remove", spoken=a))
    assert list(SpokenTo.objects.values_list("pk", flat=True)) == [uuid.UUID(b)]
    sync(client, op("spoken.clear", session=str(lesson.pk), pupil=str(pupils[0].pk), at=at(2)))
    assert not SpokenTo.objects.exists()


def test_spoken_clear_spares_a_later_tap(client, lesson, pupils):
    later = str(uuid.uuid4())
    sync(client,
         op("spoken.clear", session=str(lesson.pk), pupil=str(pupils[0].pk), at=at(1)),
         op("spoken.add", id=later, session=str(lesson.pk), pupil=str(pupils[0].pk), at=at(2)))
    sync(client, op("spoken.clear", session=str(lesson.pk), pupil=str(pupils[0].pk), at=at(1)))  # resent
    assert SpokenTo.objects.filter(pk=later).exists()


def test_attendance_last_write_wins(client, lesson, pupils):
    pupil = str(pupils[2].pk)
    sync(client, op("attendance.set", session=str(lesson.pk), pupil=pupil, present=False, at=at(2)))
    sync(client, op("attendance.set", session=str(lesson.pk), pupil=pupil, present=True, at=at(1)))  # older
    assert not SessionAttendance.objects.get(pupil=pupils[2]).present
    sync(client, op("attendance.set", session=str(lesson.pk), pupil=pupil, present=True, at=at(3)))
    assert SessionAttendance.objects.get(pupil=pupils[2]).present


# --- What can never apply ---

def test_impossible_operations_are_rejected_and_the_rest_applied(client, lesson, pupils, types):
    good = op("note.add", id=str(uuid.uuid4()), session=str(lesson.pk), pupil=str(pupils[0].pk), note_type=str(types["hp"].pk))
    bad = [
        op("note.add", id=str(uuid.uuid4()), session=str(uuid.uuid4()), pupil=str(pupils[0].pk), note_type=str(types["hp"].pk)),
        op("note.add", id=str(uuid.uuid4()), session=str(lesson.pk), pupil=str(pupils[0].pk), note_type=str(uuid.uuid4())),
        op("note.add", id=str(uuid.uuid4()), session=str(lesson.pk), pupil=str(pupils[0].pk), note_type=None, text="  "),
        op("note.add", id="not-a-uuid", session=str(lesson.pk), pupil=str(pupils[0].pk)),
        op("note.remove", note=str(uuid.uuid4())),
        op("spoken.add", id=str(uuid.uuid4()), session=str(lesson.pk), pupil=str(pupils[0].pk), at="yesterday"),
        op("reboot.laptop"),
    ]
    result = sync(client, *bad[:3], good, *bad[3:])
    assert result["applied"] == [good["op_id"]]
    assert {r["op_id"] for r in result["rejected"]} == {o["op_id"] for o in bad}
    assert Note.objects.count() == 1


def test_a_future_device_clock_is_held_to_now(client, lesson, pupils, types):
    note_id = str(uuid.uuid4())
    future = (timezone.now() + datetime.timedelta(days=30)).isoformat()
    sync(client, op("note.add", id=note_id, session=str(lesson.pk), pupil=str(pupils[0].pk), note_type=str(types["hp"].pk), at=future))
    assert Note.objects.get(pk=note_id).created_at < timezone.now() + datetime.timedelta(minutes=10)


def test_sync_refuses_malformed_bodies(client, lesson):
    assert client.post("/sync/", "not json", content_type="application/json").status_code == 400
    assert client.post("/sync/", json.dumps({"ops": "x"}), content_type="application/json").status_code == 400
    too_many = {"ops": [op("spoken.remove", spoken=str(uuid.uuid4())) for _ in range(501)]}
    assert client.post("/sync/", json.dumps(too_many), content_type="application/json").status_code == 400


def test_signed_out_sync_and_state_answer_401_so_the_device_keeps_its_queue(anon_client, teacher, lesson):
    response = anon_client.post("/sync/", json.dumps({"ops": []}), content_type="application/json")
    assert response.status_code == 401
    assert anon_client.get(f"/room/{lesson.pk}/state/").status_code == 401


# --- Lesson state ---

def test_lesson_state_carries_what_the_room_view_draws(client, timetable, lesson, pupils, types, room):
    earlier = Session.objects.create(date=D - datetime.timedelta(days=7), period="P1", klass=lesson.klass, room=room)
    carried = Note.objects.create(session=earlier, pupil=pupils[0], note_type=types["chase"], actionable=True)
    other_class = Session.objects.create(date=D, period="P2", klass=Class.objects.create(name="Choir"), room=room)
    Note.objects.create(session=other_class, pupil=pupils[0], note_type=types["chase"], actionable=True)
    Note.objects.create(session=lesson, pupil=pupils[1], note_type=types["hp"])
    Note.objects.create(session=lesson, pupil=pupils[1], note_type=types["hp"], deleted_at=timezone.now())
    SpokenTo.objects.create(session=earlier, pupil=pupils[1])
    SpokenTo.objects.create(session=lesson, pupil=pupils[1])
    SessionAttendance.objects.create(session=lesson, pupil=pupils[2], present=False)

    state = client.get(f"/room/{lesson.pk}/state/").json()
    assert state == lesson_state(lesson)
    assert state["session"] == str(lesson.pk)
    assert [t["label"] for t in state["noteTypes"]] == ["House point", "Chase homework"]  # house point first
    assert {p["name"] for p in state["pupils"]} == {"Aleya K", "Jojo P", "Sam T"}  # seated and unseated
    assert len(state["notes"]) == 1  # live notes this lesson only
    assert [(a["id"], a["when"]) for a in state["actions"]] == [(str(carried.pk), "26 Oct")]
    assert state["elsewhere"] == {str(pupils[0].pk): 1}  # the choir's open action
    assert list(state["spoken"]) == [str(pupils[1].pk)]
    assert state["absent"] == [str(pupils[2].pk)]
    assert set(state["missed"]) == {str(pupils[0].pk), str(pupils[2].pk)}


def test_room_view_embeds_the_state_and_the_sheet_templates(client, lesson, pupils, types):
    html = client.get(f"/room/{lesson.pk}/").content.decode()
    assert 'id="lesson-state"' in html
    assert 'id="tpl-note-sheet"' in html and 'id="tpl-picker"' in html and 'id="tpl-actions"' in html
    sheet = html.split('id="tpl-note-sheet"')[1].split("</template>")[0]
    assert sheet.index("House point") < sheet.index("Chase homework") < sheet.index("Free text")
    assert "<textarea" not in sheet  # the only field is behind Free text
    assert f'data-marks="{pupils[0].pk}"' in html and f'data-marks="{pupils[2].pk}"' in html


def test_room_view_with_no_input_has_no_nags(client, lesson, types):
    html = client.get(f"/room/{lesson.pk}/").content.decode()
    assert 'data-status="danger"' not in html and 'data-status="warning"' not in html
    assert "<li" not in html.split('id="log"')[1].split("</ol>")[0]


def test_inbox_lists_a_pupils_notes_newest_first(client, lesson, pupils, types):
    older = Note.objects.create(session=lesson, pupil=pupils[0], note_type=types["hp"])
    newer = Note.objects.create(session=lesson, pupil=pupils[0], text="Lovely phrasing")
    Note.objects.filter(pk=older.pk).update(created_at=timezone.now() - datetime.timedelta(minutes=5))
    Note.objects.filter(pk=newer.pk).update(created_at=timezone.now())
    html = client.get(f"/room/{lesson.pk}/inbox/{pupils[0].pk}/").content.decode()
    assert html.index("Lovely phrasing") < html.index("House point")
    assert 'data-action="back"' in html
