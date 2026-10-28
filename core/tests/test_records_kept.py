"""Deleting a plan never takes pupils' records with it: what was observed or judged stays."""

import datetime

import pytest

from assessment.models import Band, Component, Observation, Strand
from plans.models import LessonPlan, Scheme, Unit
from reports.models import SummativeJudgement
from timetable.models import Session

pytestmark = pytest.mark.django_db


@pytest.fixture
def taught(timetable, klass, room, pupils):
    unit = Unit.objects.create(scheme=Scheme.objects.create(name="Y8"), name="Blues")
    strand = Strand.objects.create(name="Performing")
    component = Component.objects.create(unit=unit, order=0, text="Steady pulse", strand=strand, next_step_default="x")
    lesson = Session.objects.create(date=datetime.date(2026, 10, 19), period="P1", klass=klass, room=room,
                                    lesson=LessonPlan.objects.create(unit=unit, order=1, objective="Blues"))
    return {"unit": unit, "strand": strand, "component": component, "lesson": lesson}


def test_a_unit_with_observations_is_kept_and_says_why(client, taught, pupils):
    Observation.objects.create(session=taught["lesson"], pupil=pupils[0], component=taught["component"], state="partly", next_step="x")
    response = client.post(f"/plan/units/{taught['unit'].pk}/delete/", follow=True)
    assert response.status_code == 200 and "part of pupils" in response.content.decode()
    assert Unit.objects.filter(pk=taught["unit"].pk).exists()


def test_a_unit_with_judgements_is_kept(client, taught, pupils):
    SummativeJudgement.objects.create(pupil=pupils[0], unit=taught["unit"], strand=taught["strand"], band=Band.objects.create(name="Secure"))
    client.post(f"/plan/units/{taught['unit'].pk}/delete/")
    assert SummativeJudgement.objects.count() == 1 and Unit.objects.filter(pk=taught["unit"].pk).exists()


def test_a_unit_without_records_can_go(client, taught):
    client.post(f"/plan/units/{taught['unit'].pk}/delete/")
    assert not Unit.objects.exists() and Session.objects.filter(pk=taught["lesson"].pk).exists()


def test_a_component_with_observations_is_kept(client, taught, pupils):
    c = taught["component"]
    Observation.objects.create(session=taught["lesson"], pupil=pupils[0], component=c, state="partly", next_step="x")
    data = {"components-TOTAL_FORMS": "1", "components-INITIAL_FORMS": "1", "components-0-id": c.pk, "components-0-order": "0",
            "components-0-text": c.text, "components-0-strand": c.strand_id, "components-0-next_step_default": "x",
            "components-0-DELETE": "on", "codes-TOTAL_FORMS": "0", "codes-INITIAL_FORMS": "0"}
    response = client.post(f"/plan/units/{taught['unit'].pk}/assessment/", data, follow=True)
    assert response.status_code == 200 and "part of pupils" in response.content.decode()
    assert Component.objects.filter(pk=c.pk).exists()
