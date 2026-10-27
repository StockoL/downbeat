import datetime

import pytest
from django.utils import timezone

from timetable.models import PupilRotation, Rotation, Session
from timetable.rotations import BadSchedule, out_of, parse_schedule, rotating

pytestmark = pytest.mark.django_db

MON = datetime.date(2026, 11, 2)
PERIODS = {"P1", "P2", "P3"}


# --- Building the grid ---

def test_rotating_steps_one_period_later_each_week():
    weeks, slots = rotating(1, ["P1", "P2", "P3"], MON + datetime.timedelta(days=3), 3)
    assert weeks == ["2026-11-02", "2026-11-09", "2026-11-16"]
    assert slots[0] == [[1, "P1"], [1, "P2"], [1, "P3"]]
    assert slots[1] == [[1, "P2"], [1, "P3"], [1, "P1"]]
    assert slots[2] == [[1, "P3"], [1, "P1"], [1, "P2"]]


def test_parse_a_pasted_schedule():
    text = "Week, Slot 1, Slot 2\n02/11/2026, Tue P1, Tue P2\n09/11/2026\tWed P3\tWed P1\n\n"
    weeks, slots = parse_schedule(text, PERIODS)
    assert weeks == ["2026-11-02", "2026-11-09"]
    assert slots == [[[1, "P1"], [1, "P2"]], [[2, "P3"], [2, "P1"]]]


@pytest.mark.parametrize("text,message", [
    ("02/11/2026, Tue P9", "isn't a period"),
    ("02/11/2026, Someday P1", "should be a day and a period"),
    ("02/11/2026, Tue P1, Tue P2\n09/11/2026, Tue P1", "the first week has 2"),
    ("02/11/2026", "no slots"),
    ("Nothing here", "No weeks found"),
])
def test_parse_refuses_what_it_cannot_read(text, message):
    with pytest.raises(BadSchedule, match=message):
        parse_schedule(text, PERIODS)


# --- Who is out ---

@pytest.fixture
def cello(pupils):
    weeks, slots = rotating(0, ["P1", "P2"], MON, 2)
    rotation = Rotation.objects.create(name="Cello", slot_count=2, weeks=weeks, slots=slots)
    PupilRotation.objects.create(pupil=pupils[0], rotation=rotation, slot_index=0)
    return rotation


def test_out_of_follows_the_rotation_week_by_week(timetable, klass, room, pupils, cello):
    p1_week1 = Session.objects.create(date=MON, period="P1", klass=klass, room=room)
    p2_week1 = Session.objects.create(date=MON, period="P2", klass=klass, room=room)
    p2_week2 = Session.objects.create(date=MON + datetime.timedelta(days=7), period="P2", klass=klass, room=room)
    week_after = Session.objects.create(date=MON + datetime.timedelta(days=14), period="P1", klass=klass, room=room)
    assert out_of(p1_week1) == {pupils[0].pk}
    assert out_of(p2_week1) == set()
    assert out_of(p2_week2) == {pupils[0].pk}  # slot 1 moved to P2
    assert out_of(week_after) == set()  # the rotation has ended


def test_room_view_and_today_show_who_is_out(client, all_day_timetable, klass, room, pupils):
    today = timezone.localdate()
    monday = today - datetime.timedelta(days=today.weekday())
    rotation = Rotation.objects.create(name="Violin", slot_count=1, weeks=[monday.isoformat()], slots=[[[today.weekday(), "All"]]])
    PupilRotation.objects.create(pupil=pupils[1], rotation=rotation, slot_index=0)
    session = Session.objects.create(date=today, period="All", klass=klass, room=room)
    assert client.get(f"/room/{session.pk}/state/").json()["out"] == [str(pupils[1].pk)]
    assert "♪ 1 out" in client.get("/?list").content.decode()


@pytest.fixture
def all_day_timetable(db):
    from timetable.models import Timetable

    return Timetable.objects.create(name="All day", periods=[{"label": "All", "start": "00:00", "end": "23:59"}])


# --- Settings ---

def test_generate_a_rotation(client, timetable):
    response = client.post("/settings/rotations/", {
        "action": "generate", "gen-name": "Mr K, guitar", "gen-day": "1", "gen-periods": ["P2", "P1"],
        "gen-first_week": "2026-11-04", "gen-weeks": "4",
    })
    rotation = Rotation.objects.get()
    assert response.url == f"/settings/rotations/{rotation.pk}/"
    assert rotation.slot_count == 2 and len(rotation.weeks) == 4
    assert rotation.slots[0] == [[1, "P1"], [1, "P2"]]  # timetable order, not tick order


def test_import_a_rotation_and_report_a_bad_row(client, timetable):
    client.post("/settings/rotations/", {"action": "import", "imp-name": "Brass", "imp-schedule": "02/11/2026, Tue P1, Tue P9"})
    assert not Rotation.objects.exists()
    client.post("/settings/rotations/", {"action": "import", "imp-name": "Brass", "imp-schedule": "02/11/2026, Tue P1, Tue P2"})
    assert Rotation.objects.get().slots == [[[1, "P1"], [1, "P2"]]]


def test_assign_unassign_and_delete(client, timetable, pupils, cello):
    page = client.get(f"/settings/rotations/{cello.pk}/").content.decode()
    assert "Mon P1" in page and "Aleya K" in page
    client.post(f"/settings/rotations/{cello.pk}/", {"pupil": pupils[1].pk, "slot_index": "1"})
    assert cello.pupils.count() == 2
    client.post(f"/settings/rotations/{cello.pk}/", {"pupil": pupils[1].pk, "slot_index": "0"})  # already in it
    assert cello.pupils.count() == 2
    entry = cello.pupils.get(pupil=pupils[1])
    client.post(f"/settings/rotations/assigned/{entry.pk}/remove/")
    assert cello.pupils.count() == 1
    client.post(f"/settings/rotations/{cello.pk}/delete/")
    assert not Rotation.objects.exists() and not PupilRotation.objects.exists()
