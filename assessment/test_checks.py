import datetime
import json
import uuid

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from assessment.models import Check, CheckResponse
from plans.models import LessonPlan, Scheme, Unit
from timetable.models import Session

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 10, 19)  # in the past: sync holds a future device clock to now
WRONG = [{"text": "Crotchet", "misconception": "Counts the beats, not the dots"},
         {"text": "Quaver", "misconception": "Reads the flag as the value"}]


@pytest.fixture
def unit(timetable):
    return Unit.objects.create(scheme=Scheme.objects.create(name="Year 8"), name="Rhythm")


@pytest.fixture
def plan(unit):
    return LessonPlan.objects.create(unit=unit, order=1, objective="Dotted notes")


@pytest.fixture
def planned(plan):
    return Check.objects.create(lesson_plan=plan, question="How long is a dotted minim?", answer="Three beats", distractors=WRONG)


@pytest.fixture
def lesson(timetable, klass, room, pupils, plan):
    return Session.objects.create(date=D, period="P1", klass=klass, room=room, lesson=plan)


def at(minutes):
    """A time in the test timetable's P1 (08:50) on the lesson's date."""
    return timezone.make_aware(datetime.datetime.combine(D, datetime.time(8, 50))) + datetime.timedelta(minutes=minutes)


def sync(client, *ops):
    return client.post("/sync/", json.dumps({"ops": list(ops)}), content_type="application/json").json()


def decide(lesson, check, decision, minutes, op_id=None, row_id=None):
    return {"op_id": op_id or str(uuid.uuid4()), "type": "check.decide", "id": row_id or str(uuid.uuid4()),
            "session": str(lesson.pk), "check": str(check.pk), "decision": decision, "at": at(minutes).isoformat()}


def hinge_fields(**fields):
    data = {"hinge-question": "", "hinge-answer": "", "hinge-threshold": "80"}
    return data | {f"hinge-{k}": v for k, v in fields.items()}


def lesson_form(plan, **hinge):
    data = {"order": str(plan.order), "objective": plan.objective}
    for prefix in ("activities", "resources"):
        data |= {f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0"}
    return data | hinge_fields(**hinge)


# --- Planning ---

def test_a_lesson_saves_its_hinge_check_with_each_wrong_answer_tagged(client, plan):
    client.post(f"/plan/lessons/{plan.pk}/", lesson_form(
        plan, question="How long is a dotted minim?", answer="Three beats", threshold="75",
        distractor_1="Crotchet", misconception_1="Counts the beats, not the dots", distractor_2="Two beats",
        misconception_2="Ignores the dot",
    ))
    check = plan.checks.get()
    assert (check.answer, check.threshold) == ("Three beats", 75)
    assert check.distractors == [{"text": "Crotchet", "misconception": "Counts the beats, not the dots"},
                                 {"text": "Two beats", "misconception": "Ignores the dot"}]


def test_a_wrong_answer_without_its_misconception_is_refused(client, plan):
    response = client.post(f"/plan/lessons/{plan.pk}/", lesson_form(
        plan, question="How long is a dotted minim?", answer="Three beats", distractor_1="Crotchet",
    ))
    assert response.status_code == 200 and not Check.objects.exists()
    assert "Say which misconception" in response.content.decode()


def test_clearing_the_question_removes_the_check(client, plan, planned):
    client.post(f"/plan/lessons/{plan.pk}/", lesson_form(plan))
    assert not Check.objects.exists()


def test_a_lesson_starts_from_another_lessons_check(client, unit, planned):
    other = LessonPlan.objects.create(unit=unit, order=2, objective="More dots")
    page = client.get(f"/plan/lessons/{other.pk}/").content.decode()
    assert "Start from another lesson's check" in page
    client.post(f"/plan/lessons/{other.pk}/hinge/copy/", {"from": str(planned.pk)})
    copy = other.checks.get()
    assert (copy.question, copy.distractors) == (planned.question, planned.distractors)
    assert "How long is a dotted minim?" in client.get(f"/plan/units/{unit.pk}/assessment/").content.decode()


def test_duplicating_a_unit_copies_its_hinge_checks(client, unit, planned):
    client.post(f"/plan/units/{unit.pk}/duplicate/")
    assert Check.objects.filter(lesson_plan__unit__name="Rhythm (copy)", question=planned.question).count() == 1


def test_a_check_is_planned_or_asked_never_both_or_neither(plan, lesson):
    with pytest.raises(IntegrityError), transaction.atomic():
        Check.objects.create(question="?", answer="!")
    with pytest.raises(IntegrityError), transaction.atomic():
        Check.objects.create(lesson_plan=plan, session=lesson, question="?", answer="!")


# --- In the room ---

def test_the_decision_is_recorded_with_how_far_in_and_a_copy_of_the_question(client, lesson, planned):
    op = decide(lesson, planned, "moved_on", 23)
    assert not sync(client, op, op)["rejected"]  # sent twice, saved once
    asked = Check.objects.get(session=lesson)
    assert (asked.decision, asked.minutes_in, asked.source, asked.question) == ("moved_on", 23, planned, planned.question)
    planned.question = "Edited later"
    planned.save()
    asked.refresh_from_db()
    assert asked.question == "How long is a dotted minim?"


def test_a_later_decision_wins_and_an_earlier_one_does_not(client, lesson, planned):
    row = str(uuid.uuid4())
    sync(client, decide(lesson, planned, "re_taught", 20, row_id=row), decide(lesson, planned, "paired", 25, row_id=row))
    sync(client, decide(lesson, planned, "moved_on", 21, row_id=row))  # older: ignored
    assert Check.objects.get(session=lesson).decision == "paired"


def test_two_devices_deciding_share_one_record(client, lesson, planned):
    sync(client, decide(lesson, planned, "re_taught", 20), decide(lesson, planned, "moved_on", 30))
    assert Check.objects.filter(session=lesson).get().decision == "moved_on"


def test_taking_a_decision_back_blanks_it_and_a_late_resend_cannot_revive_it(client, lesson, planned):
    op = decide(lesson, planned, "moved_on", 20)
    sync(client, op)
    asked = Check.objects.get(session=lesson)
    sync(client, {"op_id": str(uuid.uuid4()), "type": "check.clear", "check": str(asked.pk), "at": at(22).isoformat()})
    sync(client, {**op, "op_id": str(uuid.uuid4())})
    assert Check.objects.get(session=lesson).decision == ""


def test_impossible_decisions_are_rejected(client, lesson, planned):
    result = sync(client, decide(lesson, planned, "shrugged", 5))
    assert len(result["rejected"]) == 1
    asked = planned.ask_in(lesson, decision="paired")
    result = sync(client, decide(lesson, asked, "paired", 6))  # only a planned check can be asked
    assert len(result["rejected"]) == 1


def test_sync_never_records_a_pupils_answer(client, lesson, planned):
    sync(client, decide(lesson, planned, "moved_on", 10))
    assert not CheckResponse.objects.exists()


def test_lesson_state_carries_the_hinge_and_the_decision(client, lesson, planned):
    sync(client, decide(lesson, planned, "paired", 12))
    state = client.get(f"/room/{lesson.pk}/state/").json()
    assert state["hinge"]["question"] == "How long is a dotted minim?"
    assert state["hinge"]["distractors"] == WRONG
    assert [(d["source"], d["decision"], d["minutesIn"]) for d in state["decisions"]] == [(str(planned.pk), "paired", 12)]


def test_the_hinge_button_is_always_on_the_bar_and_greyed_without_a_check(client, timetable, klass, room, lesson, planned):
    html = client.get(f"/room/{lesson.pk}/").content.decode()
    assert 'id="tpl-hinge"' in html and 'data-decision="moved_on"' in html
    assert 'data-action="hinge" aria-keyshortcuts="H" >' in html  # enabled
    bare = Session.objects.create(date=D, period="P2", klass=klass, room=room)
    html = client.get(f"/room/{bare.pk}/").content.decode()
    assert 'data-action="hinge" aria-keyshortcuts="H" disabled' in html
    assert client.get(f"/room/{bare.pk}/state/").json()["hinge"] is None


# --- In the sweep ---

def sweep_form(**extra):
    return {"text": "", **extra}


def test_the_sweep_records_the_hinge_judgement_from_memory(client, lesson, planned):
    page = client.get(f"/sweep/{lesson.pk}/").content.decode()
    assert "3 · Hinge check" in page and "Counts the beats, not the dots" in page
    assert "Each pupil's answer" not in page  # off unless the unit opts in
    client.post(f"/sweep/{lesson.pk}/", sweep_form(hinge_decision="re_taught"))
    asked = Check.objects.get(session=lesson)
    assert (asked.decision, asked.minutes_in) == ("re_taught", None)
    client.post(f"/sweep/{lesson.pk}/", sweep_form(hinge_decision="moved_on"))
    assert Check.objects.get(session=lesson).decision == "moved_on"
    client.post(f"/sweep/{lesson.pk}/", sweep_form(hinge_decision=""))
    assert Check.objects.get(session=lesson).decision == ""


def test_a_lesson_without_a_check_has_no_hinge_section(client, timetable, klass, room, lesson):
    assert "Hinge check" not in client.get(f"/sweep/{lesson.pk}/").content.decode()


def test_pupils_answers_are_kept_only_when_the_unit_opts_in_and_with_a_decision(client, unit, lesson, planned, pupils):
    client.post(f"/sweep/{lesson.pk}/", sweep_form(hinge_decision="moved_on", **{f"response-{pupils[0].pk}": "1"}))
    assert not CheckResponse.objects.exists()  # not opted in
    unit.check_responses = True
    unit.save()
    assert "Each pupil's answer" in client.get(f"/sweep/{lesson.pk}/").content.decode()
    client.post(f"/sweep/{lesson.pk}/", sweep_form(
        hinge_decision="moved_on", **{f"response-{pupils[0].pk}": "1", f"response-{pupils[1].pk}": "0"},
    ))
    assert dict(CheckResponse.objects.values_list("pupil_id", "option")) == {pupils[0].pk: 1, pupils[1].pk: 0}
    client.post(f"/sweep/{lesson.pk}/", sweep_form(hinge_decision="moved_on", **{f"response-{pupils[1].pk}": "0"}))
    assert list(CheckResponse.objects.values_list("pupil_id", flat=True)) == [pupils[1].pk]  # a cleared answer goes


def test_answers_without_a_decision_are_not_saved(client, unit, lesson, planned, pupils):
    unit.check_responses = True
    unit.save()
    response = client.post(f"/sweep/{lesson.pk}/", sweep_form(hinge_decision="", **{f"response-{pupils[0].pk}": "1"}), follow=True)
    assert not CheckResponse.objects.exists()
    assert "kept only with a decision" in response.content.decode()
