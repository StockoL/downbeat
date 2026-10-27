import datetime
import json
import uuid

import pytest
from django.db import IntegrityError
from django.utils import timezone

from assessment.models import Component, Observation, Strand
from plans.models import LessonPlan, Scheme, Unit
from timetable.models import Session

pytestmark = pytest.mark.django_db


@pytest.fixture
def lesson(timetable, klass, room, pupils):
    unit = Unit.objects.create(scheme=Scheme.objects.create(name="Year 8"), name="Blues")
    strand = Strand.objects.create(name="Performing")
    Component.objects.create(unit=unit, order=0, text="Keeps a steady pulse", strand=strand, next_step_default="Play with the click")
    Component.objects.create(unit=unit, order=1, text="Walking bass", strand=strand, next_step_default="Add the fifth")
    plan = LessonPlan.objects.create(unit=unit, order=1, objective="Twelve-bar")
    return Session.objects.create(date=datetime.date(2026, 11, 2), period="P1", klass=klass, room=room, lesson=plan)


def at(minutes):
    return (timezone.now() - datetime.timedelta(minutes=30 - minutes)).isoformat()


def sync(client, *ops):
    return client.post("/sync/", json.dumps({"ops": list(ops)}), content_type="application/json").json()


def observe(lesson, pupil, component, state, next_step, minutes=0):
    return {"op_id": str(uuid.uuid4()), "type": "observation.add", "id": str(uuid.uuid4()), "session": str(lesson.pk),
            "pupil": str(pupil.pk), "component": str(component.pk), "state": state, "next_step": next_step, "at": at(minutes)}


def test_an_observation_from_the_seat_keeps_its_next_step(client, lesson, pupils):
    pulse = Component.objects.get(order=0)
    op = observe(lesson, pupils[0], pulse, "partly", pulse.next_step_default)
    assert not sync(client, op, op)["rejected"]  # sent twice, saved once
    o = Observation.objects.get()
    assert (o.state, o.next_step, o.assessor) == ("partly", "Play with the click", "teacher")


def test_rule_four_no_next_step_no_observation(client, lesson, pupils):
    pulse = Component.objects.get(order=0)
    result = sync(client, observe(lesson, pupils[0], pulse, "secure", "  "))
    assert len(result["rejected"]) == 1 and not Observation.objects.exists()
    with pytest.raises(IntegrityError):
        Observation.objects.create(session=lesson, pupil=pupils[0], component=pulse, state="secure")


def test_state_may_move_backwards(client, lesson, pupils):
    pulse = Component.objects.get(order=0)
    sync(client, observe(lesson, pupils[0], pulse, "secure", "Keep going", 0), observe(lesson, pupils[0], pulse, "partly", "Steady the fill", 5))
    assert list(Observation.objects.order_by("created_at").values_list("state", flat=True)) == ["secure", "partly"]


def test_change_the_next_step_and_remove(client, lesson, pupils):
    pulse = Component.objects.get(order=0)
    op = observe(lesson, pupils[0], pulse, "partly", pulse.next_step_default, 0)
    sync(client, op)
    sync(client, {"op_id": str(uuid.uuid4()), "type": "observation.update", "observation": op["id"], "next_step": "Count in aloud", "at": at(1)})
    assert Observation.objects.get().next_step == "Count in aloud"
    rejected = sync(client, {"op_id": str(uuid.uuid4()), "type": "observation.update", "observation": op["id"], "next_step": "", "at": at(2)})
    assert len(rejected["rejected"]) == 1  # can't take the next step away
    sync(client, {"op_id": str(uuid.uuid4()), "type": "observation.remove", "observation": op["id"], "at": at(3)})
    assert Observation.objects.get().deleted_at is not None


def test_lesson_state_carries_components_and_observations(client, lesson, pupils):
    pulse = Component.objects.get(order=0)
    sync(client, observe(lesson, pupils[0], pulse, "partly", "Play with the click"))
    state = client.get(f"/room/{lesson.pk}/state/").json()
    assert [(c["text"], c["nextStep"]) for c in state["components"]] == [("Keeps a steady pulse", "Play with the click"), ("Walking bass", "Add the fifth")]
    assert state["observations"][0]["state"] == "partly"
    html = client.get(f"/room/{lesson.pk}/").content.decode()
    assert 'id="tpl-observation"' in html and 'data-action="observe-sheet"' in html


def test_a_lesson_without_a_unit_has_no_components(client, timetable, klass, room):
    session = Session.objects.create(date=datetime.date(2026, 11, 2), period="P1", klass=klass, room=room)
    assert client.get(f"/room/{session.pk}/state/").json()["components"] == []


def test_the_sweep_lists_observations_and_can_bin_them(client, lesson, pupils):
    pulse = Component.objects.get(order=0)
    keep = Observation.objects.create(session=lesson, pupil=pupils[0], component=pulse, state="partly", next_step="x")
    binned = Observation.objects.create(session=lesson, pupil=pupils[1], component=pulse, state="secure", next_step="y")
    assert "Keeps a steady pulse" in client.get(f"/sweep/{lesson.pk}/").content.decode()
    client.post(f"/sweep/{lesson.pk}/", {"text": "", "bin_observation": [binned.pk]})
    keep.refresh_from_db()
    binned.refresh_from_db()
    assert keep.deleted_at is None and binned.deleted_at is not None
