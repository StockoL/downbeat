import datetime
import json
import uuid

import pytest
from django.utils import timezone

from notes import goals
from notes.models import ChecklistItem, ChecklistTick, Goal, Note, NoteType
from timetable.models import Class, Session

pytestmark = pytest.mark.django_db

MON = datetime.date(2026, 11, 2)


@pytest.fixture
def hp(db):
    return NoteType.objects.create(label="House point", icon="★", is_house_point=True)


def lesson(klass, room, day, period="P1", **kw):
    return Session.objects.create(date=MON + datetime.timedelta(days=day), period=period, klass=klass, room=room, **kw)


# --- Tallies ---

def test_a_weekly_goal_counts_lessons_with_a_note_once_each(timetable, klass, room, pupils, hp):
    goal = Goal.objects.create(text="HP in 20 lessons", target_count=20, counts_note_type=hp, week_start=MON - datetime.timedelta(days=30))
    mon, tue, wed = lesson(klass, room, 0), lesson(klass, room, 1), lesson(klass, room, 2)
    Note.objects.create(session=mon, pupil=pupils[0], note_type=hp)
    Note.objects.create(session=mon, pupil=pupils[1], note_type=hp)  # same lesson: still one
    Note.objects.create(session=tue, pupil=pupils[0], note_type=hp)
    Note.objects.create(session=wed, pupil=pupils[0], note_type=hp, deleted_at=timezone.now())  # removed: not counted
    last_week = lesson(klass, room, -3)
    Note.objects.create(session=last_week, pupil=pupils[0], note_type=hp)  # outside the week
    assert goals.tally(goal, MON + datetime.timedelta(days=2)) == 2
    assert goals.tally(goal, MON + datetime.timedelta(days=2), exclude=mon) == 1


def test_cancelled_lessons_and_other_classes(timetable, klass, room, pupils, hp):
    choir = Class.objects.create(name="Choir")
    mine = Goal.objects.create(text="8X", target_count=5, counts_note_type=hp, klass=klass, week_start=MON)
    everyone = Goal.objects.create(text="All", target_count=5, counts_note_type=hp, week_start=MON)
    Note.objects.create(session=lesson(klass, room, 0), pupil=pupils[0], note_type=hp)
    Note.objects.create(session=lesson(choir, room, 0, "P2"), pupil=pupils[0], note_type=hp)
    Note.objects.create(session=lesson(klass, room, 1, status=Session.CANCELLED), pupil=pupils[0], note_type=hp)
    assert goals.tally(mine, MON) == 1
    assert goals.tally(everyone, MON) == 2


def test_a_since_start_goal_runs_from_its_start_date(timetable, klass, room, pupils, hp):
    goal = Goal.objects.create(text="Term", target_count=50, counts_note_type=hp, scope=Goal.TERM, week_start=MON)
    for day in [0, 7, 14]:
        Note.objects.create(session=lesson(klass, room, day), pupil=pupils[0], note_type=hp)
    Note.objects.create(session=lesson(klass, room, -1), pupil=pupils[0], note_type=hp)  # before it started
    assert goals.tally(goal, MON + datetime.timedelta(days=20)) == 3


def test_goals_that_apply_to_a_lesson(timetable, klass, room, hp):
    choir = Class.objects.create(name="Choir")
    Goal.objects.create(text="Other class", target_count=1, counts_note_type=hp, klass=choir, week_start=MON)
    Goal.objects.create(text="Not yet", target_count=1, counts_note_type=hp, week_start=MON + datetime.timedelta(days=9))
    applies = Goal.objects.create(text="Mine", target_count=1, counts_note_type=hp, klass=klass, week_start=MON)
    assert goals.goals_for(lesson(klass, room, 1)) == [applies]


# --- The room view ---

def test_room_view_carries_goals_and_the_checklist(client, timetable, klass, room, pupils, hp):
    Goal.objects.create(text="HP in 20 lessons", target_count=20, counts_note_type=hp, week_start=MON)
    starter = ChecklistItem.objects.create(text="Starter", order=0)
    ChecklistItem.objects.create(text="Choir warm-up", klass=Class.objects.create(name="Choir"))
    earlier, today = lesson(klass, room, 0), lesson(klass, room, 1)
    Note.objects.create(session=earlier, pupil=pupils[0], note_type=hp)
    ChecklistTick.objects.create(session=today, checklist_item=starter, ticked_at=timezone.now())

    html = client.get(f"/room/{today.pk}/").content.decode()
    assert "data-goals" in html and 'data-action="checklist"' in html
    state = client.get(f"/room/{today.pk}/state/").json()
    assert [(g["label"], g["icon"], g["others"], g["target"]) for g in state["goals"]] == [("HP in 20 lessons", "★", 1, 20)]
    assert [i["text"] for i in state["checklist"]] == ["Starter"]
    assert list(state["ticked"]) == [str(starter.pk)]


def test_without_goals_or_a_checklist_the_bar_is_unchanged(client, timetable, klass, room):
    html = client.get(f"/room/{lesson(klass, room, 0).pk}/").content.decode()
    assert "data-goals" not in html and 'data-action="checklist"' not in html


def sync(client, *ops):
    return client.post("/sync/", json.dumps({"ops": list(ops)}), content_type="application/json").json()


def test_checklist_tick_and_untick_through_the_queue(client, timetable, klass, room):
    item = ChecklistItem.objects.create(text="Homework set")
    session = lesson(klass, room, 0)
    at = lambda m: (timezone.now() - datetime.timedelta(minutes=10 - m)).isoformat()  # noqa: E731
    tick = {"op_id": str(uuid.uuid4()), "type": "checklist.tick", "id": str(uuid.uuid4()), "session": str(session.pk), "item": str(item.pk), "at": at(0)}
    sync(client, tick, tick)
    assert ChecklistTick.objects.count() == 1
    sync(client, {"op_id": str(uuid.uuid4()), "type": "checklist.untick", "session": str(session.pk), "item": str(item.pk), "at": at(1)})
    assert not ChecklistTick.objects.exists()


def test_another_class_checklist_item_is_rejected(client, timetable, klass, room):
    item = ChecklistItem.objects.create(text="Choir warm-up", klass=Class.objects.create(name="Choir"))
    result = sync(client, {"op_id": str(uuid.uuid4()), "type": "checklist.tick", "id": str(uuid.uuid4()),
                           "session": str(lesson(klass, room, 0).pk), "item": str(item.pk), "at": timezone.now().isoformat()})
    assert len(result["rejected"]) == 1


# --- Settings ---

def formset(*rows):
    data = {"form-TOTAL_FORMS": str(len(rows)), "form-INITIAL_FORMS": "0", "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000"}
    for i, row in enumerate(rows):
        data.update({f"form-{i}-{k}": v for k, v in row.items()})
    return data


def test_settings_goals_and_checklist(client, timetable, hp):
    assert client.get("/settings/goals/").status_code == 200
    client.post("/settings/goals/", formset({"text": "HP", "counts_note_type": hp.pk, "target_count": "20", "scope": "week", "week_start": "2026-11-02"}))
    assert Goal.objects.get().target_count == 20
    assert client.get("/settings/checklist/").status_code == 200
    client.post("/settings/checklist/", formset({"order": "0", "text": "Starter"}, {"order": "1", "text": "Exit task"}))
    assert list(ChecklistItem.objects.values_list("text", flat=True)) == ["Starter", "Exit task"]
