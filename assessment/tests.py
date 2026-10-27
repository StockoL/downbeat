import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from assessment import criteria
from assessment.models import Band, Component, FeedbackCode, Strand
from plans.models import Scheme, Unit
from plans.services import duplicate_unit

pytestmark = pytest.mark.django_db


@pytest.fixture
def unit(db):
    return Unit.objects.create(scheme=Scheme.objects.create(name="Year 8"), name="Blues")


@pytest.fixture
def components(unit):
    performing = Strand.objects.create(name="Performing", order=0)
    composing = Strand.objects.create(name="Composing", order=1)
    pulse = Component.objects.create(unit=unit, order=0, text="Keeps a steady pulse", strand=performing,
                                     next_step_default="Play along with the click")
    bass = Component.objects.create(unit=unit, order=1, text="Plays a walking bass over the pulse", strand=performing,
                                    next_step_default="Add the fifth", cumulative_of=pulse)
    Component.objects.create(unit=unit, order=2, text="Writes a lyric in AAB form", strand=composing, next_step_default="Rhyme the A lines")
    FeedbackCode.objects.create(unit=unit, number=1, text="Count in before you start", component=pulse)
    return pulse, bass


def formset(prefix, rows, initial=0):
    data = {f"{prefix}-TOTAL_FORMS": str(len(rows)), f"{prefix}-INITIAL_FORMS": str(initial),
            f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"}
    for i, row in enumerate(rows):
        data.update({f"{prefix}-{i}-{k}": v for k, v in row.items()})
    return data


def test_strands_and_bands_are_teacher_defined(client, timetable):
    assert not Strand.objects.exists() and not Band.objects.exists()
    client.post("/settings/strands/", formset("form", [{"order": "0", "name": "Performing"}, {"order": "1", "name": "Listening"}]))
    client.post("/settings/bands/", formset("form", [{"order": "0", "name": "Developing"}, {"order": "1", "name": "Secure"}]))
    assert list(Strand.objects.values_list("name", flat=True)) == ["Performing", "Listening"]
    assert list(Band.objects.values_list("name", flat=True)) == ["Developing", "Secure"]


def test_a_strand_in_use_cannot_be_deleted(client, timetable, components):
    pulse, _ = components
    strand = pulse.strand
    rows = [{"id": s.pk, "order": str(s.order), "name": s.name, **({"DELETE": "on"} if s == strand else {})} for s in Strand.objects.all()]
    client.post("/settings/strands/", formset("form", rows, initial=len(rows)))
    assert Strand.objects.filter(pk=strand.pk).exists()


def test_unit_components_and_codes_page(client, timetable, unit, components):
    pulse, _ = components
    html = client.get(f"/plan/units/{unit.pk}/assessment/").content.decode()
    assert "Keeps a steady pulse" in html and "Count in before you start" in html
    data = formset("components", [{"id": c.pk, "order": str(c.order), "text": c.text, "strand": c.strand_id,
                                    "next_step_default": c.next_step_default} for c in unit.components.all()], initial=3)
    data |= formset("codes", [{"id": c.pk, "number": c.number, "text": c.text} for c in unit.feedback_codes.all()]
                    + [{"number": "2", "text": "Leave space between phrases", "component": pulse.pk}], initial=1)
    client.post(f"/plan/units/{unit.pk}/assessment/", data)
    assert unit.feedback_codes.get(number=2).component == pulse


def test_criteria_file_round_trip(client, timetable, unit, components):
    raw = client.get(f"/plan/units/{unit.pk}/criteria.json").content
    data = json.loads(raw)
    assert data["format"] == "downbeat-criteria" and len(data["components"]) == 3
    assert data["components"][1]["builds_on"] == 0
    other = Unit.objects.create(scheme=unit.scheme, name="Blues again")
    client.post(f"/plan/units/{other.pk}/criteria/import/", {"file": SimpleUploadedFile("c.json", raw, "application/json")})
    copied = list(other.components.all())
    assert [c.text for c in copied] == [c.text for c in unit.components.all()]
    assert copied[1].cumulative_of == copied[0]
    assert other.feedback_codes.get().component == copied[0]
    assert Strand.objects.count() == 2  # matched by name, not duplicated


@pytest.mark.parametrize("raw", [b"not json", b'{"format": "other"}', b'{"format": "downbeat-criteria", "version": 9}',
                                 b'{"format": "downbeat-criteria", "version": 1, "components": [{"text": "x"}]}'])
def test_a_bad_criteria_file_adds_nothing(client, timetable, unit, raw):
    client.post(f"/plan/units/{unit.pk}/criteria/import/", {"file": SimpleUploadedFile("c.json", raw)})
    assert not unit.components.exists()
    with pytest.raises(criteria.BadCriteria):
        criteria.import_into(unit, raw)


def test_duplicating_a_unit_copies_its_components_and_codes(unit, components):
    copy = duplicate_unit(unit)
    assert copy.components.count() == 3 and copy.feedback_codes.count() == 1
    assert copy.components.get(order=1).cumulative_of == copy.components.get(order=0)
