import datetime

import pytest

from assessment.models import Band, Component, Exemplar, Observation, Strand
from plans.models import LessonPlan, Scheme, Unit
from reports.models import SummativeJudgement
from timetable.models import Session

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 10, 19)


@pytest.fixture
def bands(db):
    return [Band.objects.create(name=name, order=i) for i, name in enumerate(["Developing", "Secure", "Expert"])]


@pytest.fixture
def unit(timetable, klass, room, pupils):
    unit = Unit.objects.create(scheme=Scheme.objects.create(name="Year 9"), name="Riffs")
    performing, listening = Strand.objects.create(name="Performing", order=0), Strand.objects.create(name="Listening", order=1)
    Component.objects.create(unit=unit, order=0, text="Plays a riff in time", strand=performing, next_step_default="x")
    Component.objects.create(unit=unit, order=1, text="Spots how a riff is varied", strand=listening, next_step_default="y")
    plan = LessonPlan.objects.create(unit=unit, order=1, objective="Riffs")
    unit.lesson = Session.objects.create(date=D, period="P1", klass=klass, room=room, lesson=plan)
    return unit


def grid(client, klass, unit):
    return client.get(f"/pupils/class/{klass.pk}/judgements/?unit={unit.pk}").content.decode()


def test_the_grid_shows_evidence_and_suggests_no_band(client, klass, unit, pupils, bands):
    riff = unit.components.get(order=0)
    Observation.objects.create(session=unit.lesson, pupil=pupils[0], component=riff, state="secure", next_step="x")
    Exemplar.objects.create(unit=unit, level="high", recording_path="Exemplars/riff-high.m4a")
    page = grid(client, klass, unit)
    assert "Performing" in page and "Listening" in page and "Plays a riff in time" in page
    assert "<strong>secure</strong>" in page and "Exemplars/riff-high.m4a" in page
    assert "selected>Developing" not in page and "selected>Secure" not in page and "selected>Expert" not in page


def test_saving_bands_and_taking_one_back(client, klass, unit, pupils, bands):
    performing = Strand.objects.get(name="Performing")
    url = f"/pupils/class/{klass.pk}/judgements/"
    client.post(url, {"unit": unit.pk, f"band-{pupils[0].pk}-{performing.pk}": bands[1].pk,
                      f"note-{pupils[0].pk}-{performing.pk}": "Steady in the performance"})
    j = SummativeJudgement.objects.get()
    assert (j.pupil, j.unit, j.strand, j.band, j.evidence_note) == (pupils[0], unit, performing, bands[1], "Steady in the performance")
    assert "selected>Secure" in grid(client, klass, unit)
    assert "Secure" in client.get(f"/pupils/{pupils[0].pk}/").content.decode().split("<h2>Judgements</h2>")[1]
    client.post(url, {"unit": unit.pk, f"band-{pupils[0].pk}-{performing.pk}": ""})
    assert not SummativeJudgement.objects.exists()


def test_saving_again_keeps_the_date_unless_the_band_changes(client, klass, unit, pupils, bands):
    performing = Strand.objects.get(name="Performing")
    j = SummativeJudgement.objects.create(pupil=pupils[0], unit=unit, strand=performing, band=bands[0], judged_at=D)
    url = f"/pupils/class/{klass.pk}/judgements/"
    client.post(url, {"unit": unit.pk, f"band-{pupils[0].pk}-{performing.pk}": bands[0].pk})
    j.refresh_from_db()
    assert j.judged_at == D
    client.post(url, {"unit": unit.pk, f"band-{pupils[0].pk}-{performing.pk}": bands[2].pk})
    j.refresh_from_db()
    assert (j.band, j.judged_at > D) == (bands[2], True)


def test_judgements_wait_for_bands_and_a_unit(client, timetable, klass, bands):
    assert "Once" in client.get(f"/pupils/class/{klass.pk}/judgements/").content.decode()
    Band.objects.all().delete()
    assert "Settings → Bands" in client.get(f"/pupils/class/{klass.pk}/judgements/").content.decode()


def test_a_pupil_can_carry_a_upn_for_the_export(client, timetable, pupils):
    response = client.get(f"/settings/pupils/{pupils[0].pk}/")
    assert 'name="upn"' in response.content.decode()
