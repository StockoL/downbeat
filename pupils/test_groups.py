import datetime
import json
import uuid

import pytest
from django.utils import timezone

from notes.models import Note, NoteType
from pupils.models import Group, GroupMember
from rooms.models import Seat, SeatAssignment, SeatingPlan
from timetable.models import Class, Session

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 11, 2)


@pytest.fixture
def band(klass, pupils):
    group = Group.objects.create(klass=klass, name="Riff band", working_on="Blues riff", started=D, tint=3)
    GroupMember.objects.create(group=group, pupil=pupils[0], role="drums")
    GroupMember.objects.create(group=group, pupil=pupils[1])
    return group


@pytest.fixture
def lesson(timetable, klass, room, pupils):
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=D)
    for i, pupil in enumerate(pupils):
        SeatAssignment.objects.create(seating_plan=plan, seat=Seat.objects.create(room=room, x=i * 100, y=0), pupil=pupil)
    return Session.objects.create(date=D, period="P1", klass=klass, room=room)


# --- Plan → groups ---

def test_groups_page_renders_active_and_ended(client, timetable, klass, band):
    Group.objects.create(klass=klass, name="Old trio", started=D - datetime.timedelta(days=60), ended=D - datetime.timedelta(days=20))
    html = client.get(f"/plan/classes/{klass.pk}/groups/").content.decode()
    assert "Riff band" in html and "Blues riff" in html and "Old trio" in html and "Earlier groups" in html


def test_add_a_group_with_members_and_a_free_tint(client, timetable, klass, pupils, band):
    client.post(f"/plan/classes/{klass.pk}/groups/", {"name": "Keys", "working_on": "", "started": "2026-11-02", "members": [pupils[2].pk]})
    keys = Group.objects.get(name="Keys")
    assert list(keys.members.values_list("pupil", flat=True)) == [pupils[2].pk]
    assert keys.tint != band.tint


def test_a_pupil_is_in_one_active_group_per_class(client, timetable, klass, pupils, band):
    client.post(f"/plan/classes/{klass.pk}/groups/", {"name": "Keys", "started": "2026-11-02", "members": [pupils[0].pk]})
    assert not Group.objects.filter(name="Keys").exists()


def test_add_member_set_role_remove_and_end(client, timetable, klass, pupils, band):
    client.post(f"/plan/groups/{band.pk}/members/", {"pupil": pupils[2].pk, "role": "keys"})
    member = band.members.get(pupil=pupils[2])
    assert member.role == "keys"
    client.post(f"/plan/members/{member.pk}/role/", {"role": "  vocals "})
    member.refresh_from_db()
    assert member.role == "vocals"
    client.post(f"/plan/members/{member.pk}/remove/")
    assert band.members.count() == 2
    client.post(f"/plan/groups/{band.pk}/end/")
    band.refresh_from_db()
    assert band.ended == timezone.localdate()
    assert band.members.count() == 2  # history keeps who was in it


# --- In the room ---

def test_room_view_tints_members_and_offers_the_group(client, lesson, band, pupils):
    html = client.get(f"/room/{lesson.pk}/").content.decode()
    assert html.count("seat group-tint-3") == 2
    assert f'data-group="{band.pk}"' in html and "Riff band" in html
    assert json.loads(html.split('id="lesson-state" type="application/json">')[1].split("</script>")[0])["groups"] == [
        {"id": str(band.pk), "name": "Riff band"},
    ]


def test_ended_groups_leave_the_room(client, lesson, band):
    Group.objects.filter(pk=band.pk).update(ended=D)
    html = client.get(f"/room/{lesson.pk}/").content.decode()
    assert "seat group-tint-" not in html and "room-unseated__pupil group-tint-" not in html
    assert "Riff band" not in html


def test_plan_editor_tints_members(client, lesson, band):
    plan = SeatingPlan.objects.get()
    assert client.get(f"/plan/seating/{plan.pk}/").content.decode().count("seat group-tint-3") == 2


def sync(client, *ops):
    return client.post("/sync/", json.dumps({"ops": list(ops)}), content_type="application/json").json()


def note_op(**fields):
    return {"op_id": str(uuid.uuid4()), "type": "note.add", "id": str(uuid.uuid4()), "at": timezone.now().isoformat(), **fields}


def test_a_group_note_is_one_note_for_the_group(client, lesson, band):
    hp = NoteType.objects.create(label="House point", icon="★", is_house_point=True)
    result = sync(client, note_op(session=str(lesson.pk), group=str(band.pk), note_type=str(hp.pk)))
    assert not result["rejected"]
    note = Note.objects.get()
    assert note.group == band and note.pupil is None
    state = client.get(f"/room/{lesson.pk}/state/").json()
    assert state["notes"][0]["group"] == str(band.pk) and state["notes"][0]["pupil"] is None


def test_a_note_needs_exactly_one_pupil_or_group(client, lesson, band, pupils):
    neither = note_op(session=str(lesson.pk), text="x")
    both = note_op(session=str(lesson.pk), pupil=str(pupils[0].pk), group=str(band.pk), text="x")
    other_class = Group.objects.create(klass=Class.objects.create(name="Choir"), name="Altos", started=D)
    elsewhere = note_op(session=str(lesson.pk), group=str(other_class.pk), text="x")
    result = sync(client, neither, both, elsewhere)
    assert len(result["rejected"]) == 3 and not Note.objects.exists()


def test_a_group_with_notes_cannot_be_deleted_but_can_be_ended(lesson, band):
    from django.db.models import ProtectedError

    Note.objects.create(session=lesson, group=band, text="Tight ending")
    with pytest.raises(ProtectedError):
        band.delete()
