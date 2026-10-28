import datetime

import pytest
from django.db import IntegrityError, transaction

from assessment.forms import parse_at
from assessment.models import Component, Feedback, FeedbackCode, Observation, Strand
from plans.models import LessonPlan, Scheme, Unit
from pupils.models import Group, GroupMember
from timetable.models import Session

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 10, 19)


@pytest.fixture
def unit(timetable):
    unit = Unit.objects.create(scheme=Scheme.objects.create(name="Year 9"), name="Riffs")
    strand = Strand.objects.create(name="Performing")
    Component.objects.create(unit=unit, order=0, text="Plays a riff in time", strand=strand, next_step_default="Lock in with the snare")
    Component.objects.create(unit=unit, order=1, text="Layers a second riff", strand=strand, next_step_default="Leave space")
    return unit


@pytest.fixture
def lesson(unit, klass, room, pupils):
    plan = LessonPlan.objects.create(unit=unit, order=1, objective="Riffs on keyboards")
    return Session.objects.create(date=D, period="P1", klass=klass, room=room, lesson=plan)


@pytest.fixture
def band(klass, pupils):
    group = Group.objects.create(klass=klass, name="Band 1", started=D)
    for pupil in pupils[:2]:
        GroupMember.objects.create(group=group, pupil=pupil)
    return group


def write(client, lesson, **fields):
    return client.post(f"/sweep/{lesson.pk}/feedback/", {"done_well": "", "develop": "", "how": "", **fields})


# --- Feedback ---

def test_three_part_feedback_for_a_pupil(client, lesson, pupils, unit):
    riff = unit.components.get(order=0)
    write(client, lesson, who=f"pupil:{pupils[0].pk}", component=riff.pk, done_well="Steady pulse",
          develop="The fill rushes", how="Count the fill out loud")
    f = Feedback.objects.get()
    assert (f.pupil, f.component, f.how) == (pupils[0], riff, "Count the fill out loud")
    assert "The fill rushes" in client.get(f"/sweep/{lesson.pk}/feedback/").content.decode()
    assert "The fill rushes" in client.get(f"/pupils/{pupils[0].pk}/").content.decode()
    assert "Feedback for this lesson</a> (1 written)" in client.get(f"/sweep/{lesson.pk}/").content.decode()


def test_feedback_needs_someone_and_something_to_say(client, lesson, pupils):
    assert write(client, lesson, who=f"pupil:{pupils[0].pk}").status_code == 200
    assert write(client, lesson, develop="Steadier").status_code == 200
    assert not Feedback.objects.exists()


def test_group_feedback_shows_on_each_members_page(client, lesson, pupils, band):
    write(client, lesson, who=f"group:{band.pk}", develop="Agree an ending")
    assert Feedback.objects.get().group == band
    assert "Agree an ending" in client.get(f"/pupils/{pupils[1].pk}/").content.decode()
    assert "Agree an ending" not in client.get(f"/pupils/{pupils[2].pk}/").content.decode()


def test_a_recording_only_for_pupils_whose_families_agreed(client, lesson, pupils):
    response = write(client, lesson, who=f"pupil:{pupils[0].pk}", develop="Bar 9", recording_path="Recordings/riff.m4a")
    assert "permitted for" in response.content.decode() and not Feedback.objects.exists()
    pupils[0].recording_permitted = True
    pupils[0].save()
    write(client, lesson, who=f"pupil:{pupils[0].pk}", develop="Bar 9, left hand", recording_path="Recordings/riff.m4a", recording_at="1:42")
    f = Feedback.objects.get()
    assert (f.recording_seconds, f.at) == (102, "1:42")
    assert "at 1:42" in client.get(f"/pupils/{pupils[0].pk}/").content.decode()


def test_a_group_recording_needs_every_member_permitted(client, lesson, pupils, band):
    pupils[0].recording_permitted = True
    pupils[0].save()
    response = write(client, lesson, who=f"group:{band.pk}", develop="Tighter", recording_path="Recordings/band1.m4a")
    assert str(pupils[1]) in response.content.decode() and not Feedback.objects.exists()


def test_a_time_needs_a_recording_and_reads_as_minutes_and_seconds(client, lesson, pupils):
    assert "needs the recording" in write(client, lesson, who=f"pupil:{pupils[0].pk}", develop="x", recording_at="0:30").content.decode()
    assert [parse_at(t) for t in ("", "1:42", "90", "10:05")] == [None, 102, 90, 605]
    for bad in ("1:75", "a:10", "1:2:3", "-5"):
        with pytest.raises(ValueError):
            parse_at(bad)
    with pytest.raises(IntegrityError), transaction.atomic():
        Feedback.objects.create(session=lesson, pupil=pupils[0], develop="x", recording_seconds=5)


def test_feedback_is_for_a_pupil_or_a_group_not_both(lesson, pupils, band):
    with pytest.raises(IntegrityError), transaction.atomic():
        Feedback.objects.create(session=lesson, pupil=pupils[0], group=band, develop="x")
    with pytest.raises(IntegrityError), transaction.atomic():
        Feedback.objects.create(session=lesson, develop="x")


def test_delete_feedback(client, lesson, pupils):
    f = Feedback.objects.create(session=lesson, pupil=pupils[0], develop="x")
    assert client.post(f"/sweep/feedback/{f.pk}/delete/").url == f"/sweep/{lesson.pk}/feedback/"
    assert not Feedback.objects.exists()


# --- Codes as a slide ---

def test_feedback_codes_as_a_slide_with_nothing_about_any_pupil(client, lesson, unit, pupils):
    FeedbackCode.objects.create(unit=unit, number=1, text="Count in before you start", action="Count four out loud")
    page = client.get(f"/plan/units/{unit.pk}/codes/").content.decode()
    assert "Count in before you start" in page and "Count four out loud" in page and 'class="projector"' in page
    assert not any(str(p) in page for p in pupils)
    room = client.get(f"/room/{lesson.pk}/").content.decode()
    assert f"/plan/units/{unit.pk}/codes/" in room  # in the overflow menu, not on the bar


def test_no_codes_link_in_the_room_without_codes(client, lesson, unit):
    assert f"/plan/units/{unit.pk}/codes/" not in client.get(f"/room/{lesson.pk}/").content.decode()


# --- The class-by-component view ---

def test_each_pupils_latest_state_and_nothing_added_up(client, klass, lesson, unit, pupils):
    riff = unit.components.get(order=0)
    Observation.objects.create(session=lesson, pupil=pupils[0], component=riff, state="secure", next_step="x")
    Observation.objects.create(session=lesson, pupil=pupils[0], component=riff, state="partly", next_step="x")  # later
    Observation.objects.create(session=lesson, pupil=pupils[1], component=riff, state="secure", next_step="x", assessor="self")
    page = client.get(f"/pupils/class/{klass.pk}/components/").content.decode()
    assert page.count('data-state="partly"') == 1 and 'data-state="secure"' not in page  # self isn't the teacher's
    assert "%" not in page.split("<table", 1)[1]
    page = client.get(f"/pupils/class/{klass.pk}/components/?assessor=self").content.decode()
    assert page.count('data-state="secure"') == 1


def test_the_components_tab_waits_for_a_unit(client, timetable, klass):
    assert "Once" in client.get(f"/pupils/class/{klass.pk}/components/").content.decode()


# --- Self and peer in batch ---

def test_self_assessment_for_the_class_in_one_go(client, klass, lesson, unit, pupils):
    riff = unit.components.get(order=0)
    assert "Plays a riff in time" in client.get(f"/pupils/class/{klass.pk}/self-peer/").content.decode()
    client.post(f"/pupils/class/{klass.pk}/self-peer/", {
        "session": lesson.pk, "component": riff.pk, "assessor": "self",
        f"state-{pupils[0].pk}": "secure", f"state-{pupils[1].pk}": "not_yet", f"state-{pupils[2].pk}": "",
    })
    made = Observation.objects.order_by("state")
    assert [(o.pupil, o.state, o.assessor, o.next_step) for o in made] == [
        (pupils[1], "not_yet", "self", "Lock in with the snare"), (pupils[0], "secure", "self", "Lock in with the snare"),
    ]


def test_self_and_peer_refuses_a_teacher_entry_or_a_stray_component(client, klass, lesson, pupils):
    other = Component.objects.create(unit=Unit.objects.create(scheme=Scheme.objects.create(name="Y7"), name="Other"), order=0,
                                     text="Elsewhere", strand=Strand.objects.first(), next_step_default="x")
    client.post(f"/pupils/class/{klass.pk}/self-peer/", {"session": lesson.pk, "component": other.pk, "assessor": "self",
                                                        f"state-{pupils[0].pk}": "secure"})
    riff = Component.objects.get(text="Plays a riff in time")
    client.post(f"/pupils/class/{klass.pk}/self-peer/", {"session": lesson.pk, "component": riff.pk, "assessor": "teacher",
                                                        f"state-{pupils[0].pk}": "secure"})
    assert not Observation.objects.exists()
