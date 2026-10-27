import datetime

import pytest

from notes.models import Note, NoteType
from plans.models import ActivityStatus, LessonPlan, PlanActivity, Scheme, SessionReflection, Unit
from plans.sweep import give_to_members, next_for_class
from pupils.models import Group, GroupMember
from timetable.models import Class, Session

pytestmark = pytest.mark.django_db

TUE = datetime.date(2026, 10, 27)


@pytest.fixture
def lesson(db):
    unit = Unit.objects.create(scheme=Scheme.objects.create(name="Year 8"), name="Blues")
    plan = LessonPlan.objects.create(unit=unit, order=1, objective="Twelve-bar")
    for order, (text, minutes) in enumerate([("Warm-up", 5), ("Riff in pairs", 25), ("Perform", 15)]):
        PlanActivity.objects.create(lesson_plan=plan, order=order, text=text, minutes=minutes)
    return plan


@pytest.fixture
def tuesdays(timetable, klass, room, lesson):
    """This Tuesday's lesson, another class and a cancelled one in between, then next Tuesday's."""
    this = Session.objects.create(date=TUE, period="P1", klass=klass, room=room, lesson=lesson)
    Session.objects.create(date=TUE + datetime.timedelta(days=2), period="P1", klass=Class.objects.create(name="Choir"), room=room)
    Session.objects.create(date=TUE + datetime.timedelta(days=3), period="P1", klass=klass, room=room, status=Session.CANCELLED)
    following = Session.objects.create(date=TUE + datetime.timedelta(days=7), period="P1", klass=klass, room=room)
    return this, following


def activity_ids(lesson):
    return [str(a.pk) for a in lesson.activities.all()]


def sweep(client, session, statuses, carry=(), binned=(), text="", tags=()):
    data = {f"status-{a}": s for a, s in statuses.items()} | {"carry": list(carry), "bin": list(binned), "text": text, "tags": list(tags)}
    return client.post(f"/sweep/{session.pk}/", data)


def test_next_for_class_skips_other_classes_and_cancelled(tuesdays):
    this, following = tuesdays
    assert next_for_class(this) == following


def test_unfinished_activity_from_tuesday_is_a_prompt_on_the_following_tuesday(client, tuesdays, lesson):
    """Phase 4's "done when", part one."""
    this, following = tuesdays
    warm, riff, perform = activity_ids(lesson)
    sweep(client, this, {warm: "done", riff: "partial", perform: "not_reached"}, carry=[riff, perform])
    carried = ActivityStatus.objects.filter(carried_to_session=following)
    assert sorted(c.plan_activity.text for c in carried) == ["Perform", "Riff in pairs"]
    html = client.get(f"/room/{following.pk}/").content.decode()
    assert "Carried forward" in html and "Riff in pairs" in html and "from Tue 27 Oct" in html
    assert "Riff in pairs" in client.get(f"/sweep/{following.pk}/").content.decode()


def test_a_done_activity_is_never_carried(client, tuesdays, lesson):
    this, _ = tuesdays
    warm, _, _ = activity_ids(lesson)
    sweep(client, this, {warm: "done"}, carry=[warm])
    assert ActivityStatus.objects.get().carried_to_session is None


def test_unticking_carry_on_a_second_sweep_takes_it_back(client, tuesdays, lesson):
    this, _ = tuesdays
    _, riff, _ = activity_ids(lesson)
    sweep(client, this, {riff: "partial"}, carry=[riff])
    sweep(client, this, {riff: "partial"}, carry=[])
    assert ActivityStatus.objects.get().carried_to_session is None


def test_sweep_saves_the_reflection_bins_notes_and_marks_taught(client, tuesdays, lesson, pupils):
    this, _ = tuesdays
    hp = NoteType.objects.create(label="House point")
    keep = Note.objects.create(session=this, pupil=pupils[0], note_type=hp)
    binned = Note.objects.create(session=this, pupil=pupils[1], note_type=hp)
    response = sweep(client, this, {}, binned=[binned.pk], text="  Pairs ran long  ", tags=["TS4", "TS99"])
    assert response.url == "/sweep/?date=2026-10-27"
    reflection = SessionReflection.objects.get(session=this)
    assert reflection.text == "Pairs ran long" and reflection.tags == ["TS4"]
    keep.refresh_from_db()
    binned.refresh_from_db()
    assert keep.deleted_at is None and binned.deleted_at is not None
    this.refresh_from_db()
    assert this.status == Session.TAUGHT


def test_sweep_home_ticks_swept_sessions_and_highlights_the_first_unswept(client, tuesdays, klass, room):
    this, _ = tuesdays
    later = Session.objects.create(date=TUE, period="P2", klass=klass, room=room)
    SessionReflection.objects.create(session=this)
    html = client.get("/sweep/?date=2026-10-27").content.decode()
    assert "✓ swept" in html
    first = html.split("data-current")[1]
    assert f"/sweep/{later.pk}/" in first.split("</li>")[0]


def test_a_group_note_can_be_given_to_each_member_once(client, tuesdays, klass, pupils):
    this, _ = tuesdays
    band = Group.objects.create(klass=klass, name="Band", started=TUE)
    for pupil in pupils[:2]:
        GroupMember.objects.create(group=band, pupil=pupil)
    note = Note.objects.create(session=this, group=band, text="Tight ending")
    client.post(f"/sweep/notes/{note.pk}/members/")
    assert give_to_members(note) == 0  # already given
    copies = Note.objects.filter(session=this, pupil__isnull=False)
    assert sorted(str(n.pupil) for n in copies) == ["Aleya K", "Jojo P"]
    assert all(n.text == "Tight ending" for n in copies)
    assert Note.objects.filter(group=band).count() == 1  # the group note stays


def test_sweep_pages_render(client, tuesdays):
    this, _ = tuesdays
    assert client.get("/sweep/").status_code == 200
    assert client.get(f"/sweep/{this.pk}/").status_code == 200


def test_a_reflection_can_spawn_a_goal(client, tuesdays, klass):
    from django.utils import timezone

    from notes.models import Goal

    this, _ = tuesdays
    hp = NoteType.objects.create(label="House point", is_house_point=True)
    client.post(f"/sweep/{this.pk}/", {
        "text": "Quiet ones got nothing", "goal_text": "A house point in 15 lessons", "goal_note_type": hp.pk,
        "goal_target": "15", "goal_this_class": "on",
    })
    goal = Goal.objects.get()
    assert (goal.text, goal.target_count, goal.klass, goal.week_start) == ("A house point in 15 lessons", 15, klass, timezone.localdate())
    assert SessionReflection.objects.get(session=this).spawned_goal == goal
    assert "Became the goal" in client.get(f"/sweep/{this.pk}/").content.decode()


def test_an_incomplete_goal_is_not_made(client, tuesdays):
    from notes.models import Goal

    this, _ = tuesdays
    client.post(f"/sweep/{this.pk}/", {"text": "x", "goal_text": "Something", "goal_target": ""})
    response = client.post(f"/sweep/{this.pk}/", {"text": "x", "goal_text": "Something", "goal_note_type": "nonsense", "goal_target": "5"})
    assert response.status_code == 302
    assert not Goal.objects.exists()
    assert SessionReflection.objects.filter(session=this).exists()  # the sweep itself still saved
