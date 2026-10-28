import datetime
import json

import pytest
from django.apps import apps
from django.core.management import call_command
from django.template import Context, Template
from django.utils import timezone

from assessment import recordings
from assessment.models import Check, CheckResponse, Component, Exemplar, Feedback, Observation, Strand
from core.data import EXPORT_APPS, export_pupil
from notes.models import Note, SpokenTo
from plans.models import LessonPlan, Scheme, Unit
from pupils.models import FlagType, Group, GroupMember, Loan, LoanItem, PupilFlag, Relationship
from rooms.models import Seat, SeatAssignment, SeatingPlan
from timetable.models import Pupil, PupilRotation, Rotation, Session, SessionAttendance

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 10, 19)


@pytest.fixture
def unit(timetable):
    unit = Unit.objects.create(scheme=Scheme.objects.create(name="Year 9"), name="Riffs")
    strand = Strand.objects.create(name="Performing")
    Component.objects.create(unit=unit, order=0, text="Plays a riff in time", strand=strand, next_step_default="Lock in")
    Component.objects.create(unit=unit, order=1, text="Layers a second riff", strand=strand, next_step_default="Leave space")
    return unit


@pytest.fixture
def lesson(unit, klass, room, pupils):
    plan = LessonPlan.objects.create(unit=unit, order=1, objective="Riffs on keyboards")
    return Session.objects.create(date=D, period="P1", klass=klass, room=room, lesson=plan)


@pytest.fixture
def ada(pupils):
    pupil = pupils[0]
    pupil.recording_permitted = pupil.exemplar_reuse_permitted = True
    pupil.save()
    return pupil


# --- The exemplar bank ---

def test_an_exemplar_from_a_pupil_whose_family_agreed(client, unit, ada, pupils):
    riff = unit.components.get(order=0)
    page = client.get(f"/plan/units/{unit.pk}/assessment/").content.decode()
    assert "Add an exemplar" in page and str(ada) in page and str(pupils[1]) not in page.split('id="exemplars"')[1]
    client.post(f"/plan/units/{unit.pk}/exemplars/", {
        "exemplar-component": riff.pk, "exemplar-level": "high", "exemplar-recording_path": "Exemplars/riff-high.m4a",
        "exemplar-note": "Listen to the hi-hat", "exemplar-source_pupil": ada.pk,
    })
    e = Exemplar.objects.get()
    assert (e.unit, e.component, e.level, e.source_pupil) == (unit, riff, "high", ada)
    assert "Exemplars/riff-high.m4a" in client.get(f"/plan/units/{unit.pk}/assessment/").content.decode()


def test_an_exemplar_is_refused_from_a_pupil_without_reuse_permission(client, unit, pupils):
    client.post(f"/plan/units/{unit.pk}/exemplars/", {
        "exemplar-level": "mid", "exemplar-recording_path": "x.m4a", "exemplar-source_pupil": pupils[1].pk,
    })
    assert not Exemplar.objects.exists()


def test_an_exemplar_without_a_pupil_and_removing_one(client, unit):
    client.post(f"/plan/units/{unit.pk}/exemplars/", {"exemplar-level": "low", "exemplar-recording_path": "Teacher demo.m4a"})
    e = Exemplar.objects.get()
    assert e.source_pupil is None
    client.post(f"/plan/exemplars/{e.pk}/delete/")
    assert not Exemplar.objects.exists()


# --- Recordings and the timeline ---

def test_a_recording_joins_the_pupils_timeline_oldest_first(client, lesson, unit, ada, klass, room):
    riff = unit.components.get(order=0)
    later = Session.objects.create(date=D + datetime.timedelta(days=7), period="P1", klass=klass, room=room, lesson=lesson.lesson)
    for session, state, path in ((later, "secure", "Rec/week-2.m4a"), (lesson, "partly", "Rec/week-1.m4a")):
        response = client.post(f"/pupils/{ada.pk}/", {
            "add_recording": "", "recording-lesson": session.pk, "recording-component": riff.pk,
            "recording-state": state, "recording-recording_path": path,
        })
        assert response.status_code == 302
    o = Observation.objects.get(recording_path="Rec/week-1.m4a")
    assert (o.next_step, o.state, o.assessor) == ("", "partly", "teacher")  # the recording is enough to keep it
    page = client.get(f"/pupils/{ada.pk}/").content.decode()
    timeline = page.split('id="timeline"')[1]
    assert timeline.index("week-1") < timeline.index("week-2")


def test_no_recordings_for_a_pupil_without_permission(client, lesson, unit, pupils):
    page = client.get(f"/pupils/{pupils[1].pk}/").content.decode()
    assert 'name="add_recording"' not in page and "Recordings aren't permitted for" in page
    client.post(f"/pupils/{pupils[1].pk}/", {
        "add_recording": "", "recording-lesson": lesson.pk, "recording-component": unit.components.first().pk,
        "recording-state": "partly", "recording-recording_path": "x.m4a",
    })
    assert not Observation.objects.exists()


def test_feedback_recordings_are_on_the_timeline_at_their_moment(client, lesson, ada):
    Feedback.objects.create(session=lesson, pupil=ada, develop="Rushes the fill",
                            recording_path="https://media.example/riff.m4a", recording_seconds=102)
    page = client.get(f"/pupils/{ada.pk}/").content.decode().split('id="timeline"')[1]
    assert 'href="https://media.example/riff.m4a#t=102"' in page and "at 1:42" in page and "Rushes the fill" in page


def test_a_recording_reads_as_a_link_or_a_path():
    tag = Template("{% load recordings %}{% recording path seconds %}")
    assert tag.render(Context({"path": "Rec/a.m4a", "seconds": 65})) == "<code>Rec/a.m4a</code> at 1:05"
    assert 'href="https://x.test/a.m4a"' in tag.render(Context({"path": "https://x.test/a.m4a", "seconds": None}))
    assert tag.render(Context({"path": "<b>", "seconds": None})) == "<code>&lt;b&gt;</code>"


# --- Removing what may no longer be kept ---

@pytest.fixture
def recorded(lesson, unit, ada, pupils, klass):
    riff = unit.components.get(order=0)
    band = Group.objects.create(klass=klass, name="Band 1", started=D)
    GroupMember.objects.create(group=band, pupil=ada)
    return {
        "only_recording": Observation.objects.create(session=lesson, pupil=ada, component=riff, state="partly", recording_path="Rec/1.m4a"),
        "with_step": Observation.objects.create(session=lesson, pupil=ada, component=riff, state="secure", next_step="Keep going",
                                                recording_path="Rec/2.m4a"),
        "feedback": Feedback.objects.create(session=lesson, pupil=ada, develop="x", recording_path="Rec/3.m4a", recording_seconds=5),
        "group": Feedback.objects.create(session=lesson, group=band, develop="y", recording_path="Rec/4.m4a"),
        "exemplar": Exemplar.objects.create(unit=unit, level="high", recording_path="Rec/5.m4a", source_pupil=ada),
    }


def test_nothing_is_due_while_permission_holds(recorded):
    assert recordings.paths(recordings.due()) == []


def test_past_the_delete_by_date_every_reference_goes(recorded, ada):
    ada.recordings_delete_by = timezone.localdate()
    ada.save()
    assert sorted(recordings.purge()) == ["Rec/1.m4a", "Rec/2.m4a", "Rec/3.m4a", "Rec/4.m4a", "Rec/5.m4a"]
    assert not Observation.objects.filter(pk=recorded["only_recording"].pk).exists()  # kept only for its recording
    kept = Observation.objects.get(pk=recorded["with_step"].pk)
    assert (kept.recording_path, kept.next_step) == ("", "Keep going")
    assert list(Feedback.objects.values_list("recording_path", "recording_seconds")) == [("", None), ("", None)]
    assert not Exemplar.objects.exists()


def test_withdrawing_reuse_removes_only_the_exemplars(recorded, ada):
    ada.exemplar_reuse_permitted = False
    ada.save()
    assert recordings.purge() == ["Rec/5.m4a"]
    assert Observation.objects.exclude(recording_path="").count() == 2


def test_the_data_page_lists_them_and_removes_them_once(client, recorded, ada):
    ada.recording_permitted = False
    ada.save()
    page = client.get("/settings/data/").content.decode()
    assert "Rec/1.m4a" in page and "Remove these references" in page
    client.post("/settings/data/recordings/")
    page = client.get("/settings/data/").content.decode()
    assert "Delete these files" not in page and "Rec/1.m4a" in page and "Removed." in page
    assert "Rec/1.m4a" not in client.get("/settings/data/").content.decode()  # the list shows once
    assert not Exemplar.objects.exists()


def test_the_command_lists_then_removes(recorded, ada, capsys):
    ada.recordings_delete_by = timezone.localdate() - datetime.timedelta(days=1)
    ada.save()
    call_command("purge_recordings", "--dry-run")
    assert "Would remove" in capsys.readouterr().out and Exemplar.objects.exists()
    call_command("purge_recordings")
    assert "Rec/5.m4a" in capsys.readouterr().out and not Exemplar.objects.exists()


# --- Everything held about one pupil ---

def test_the_pupil_export_follows_every_link_to_a_pupil(client, lesson, unit, ada, pupils, klass, room, recorded):
    other = pupils[1]
    Note.objects.create(session=lesson, pupil=ada, text="Brought own guitar")
    SpokenTo.objects.create(session=lesson, pupil=ada)
    SessionAttendance.objects.create(session=lesson, pupil=ada, present=False)
    PupilFlag.objects.create(pupil=ada, flag_type=FlagType.objects.create(label="Hearing", colour=1))
    Relationship.objects.create(pupil_a=min(ada, other, key=lambda p: p.pk), pupil_b=max(ada, other, key=lambda p: p.pk), kind="pair_well")
    Loan.objects.create(item=LoanItem.objects.create(name="Headphones"), pupil=ada, out_at=timezone.now())
    PupilRotation.objects.create(pupil=ada, rotation=Rotation.objects.create(name="Violin", slot_count=1), slot_index=0)
    plan = SeatingPlan.objects.create(klass=klass, room=room, name="Plan", active_from=D)
    SeatAssignment.objects.create(seating_plan=plan, seat=Seat.objects.create(room=room, x=0, y=0), pupil=ada)
    asked = Check.objects.create(session=lesson, question="?", answer="!", decision="moved_on")
    CheckResponse.objects.create(check_asked=asked, pupil=ada, option=0)

    data = json.loads(client.get(f"/pupils/{ada.pk}/export.json").content)
    assert data["pupil"] == str(ada) and data["classes"] == [str(klass)]
    exported = {r["model"] for r in data["records"]}
    linked = {m._meta.label_lower for app in EXPORT_APPS for m in apps.get_app_config(app).get_models()
              if any(f.many_to_one and f.related_model is Pupil for f in m._meta.get_fields())}
    assert linked <= exported, linked - exported
    assert str(other) not in json.dumps(data)
    assert "Rec/4.m4a" in json.dumps(data)  # the group's feedback she was part of
    assert export_pupil(other).count("Brought own guitar") == 0
