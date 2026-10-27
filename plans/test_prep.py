import datetime

import pytest
from django.utils import timezone

from notes.models import Note, NoteType
from plans.models import LessonPlan, PrepItem, Resource, Scheme, Unit
from plans.prep import next_teaching_day, refresh
from timetable.models import Session

pytestmark = pytest.mark.django_db

FRI = datetime.date(2026, 10, 30)


@pytest.fixture
def printing(db):
    unit = Unit.objects.create(scheme=Scheme.objects.create(name="Year 8"), name="Blues")
    lesson = LessonPlan.objects.create(unit=unit, order=4, objective="Lyrics")
    Resource.objects.create(lesson_plan=lesson, title="Lyric sheet", needs_print=True, copies=30, path_or_url="Music/Y8/lyrics.pdf")
    Resource.objects.create(lesson_plan=lesson, title="Keyboards", setup_note="Headphones on every keyboard")
    Resource.objects.create(lesson_plan=lesson, title="Slides", path_or_url="Music/Y8/slides.pptx")  # nothing to do
    return lesson


@pytest.fixture
def monday(timetable, klass, room, printing):
    return Session.objects.create(date=FRI + datetime.timedelta(days=3), period="P1", klass=klass, room=room, lesson=printing)


def texts(session):
    return sorted(session.prep_items.values_list("text", flat=True))


def test_next_teaching_day_skips_the_weekend(monday):
    assert next_teaching_day(FRI) == monday.date


def test_prep_lists_tomorrows_printing_without_being_told(client, monday):
    """Phase 4's "done when", part two: nothing to set up but the lesson plan's resources."""
    html = client.get(f"/sweep/prep/?date={monday.date.isoformat()}").content.decode()
    assert "Print 30 × Lyric sheet (Music/Y8/lyrics.pdf)" in html
    assert "Set up: Keyboards: Headphones on every keyboard" in html
    assert "Slides" not in html


def test_prep_lists_the_classs_open_actions_to_chase(client, timetable, monday, klass, room, pupils):
    earlier = Session.objects.create(date=FRI, period="P1", klass=klass, room=room)
    chase = NoteType.objects.create(label="Chase homework", is_actionable_default=True)
    Note.objects.create(session=earlier, pupil=pupils[0], note_type=chase, actionable=True)
    Note.objects.create(session=earlier, pupil=pupils[1], note_type=chase, actionable=True, done_at=timezone.now())
    refresh(monday)
    assert "Chase: Aleya K · Chase homework" in texts(monday)
    assert not any("Jojo" in t for t in texts(monday))


def test_refresh_follows_the_plan_but_keeps_ticked_items(monday, printing):
    refresh(monday)
    sheet = monday.prep_items.get(text__startswith="Print")
    sheet.done_at = timezone.now()
    sheet.save()
    Resource.objects.filter(title="Keyboards").delete()
    Resource.objects.filter(title="Lyric sheet").delete()
    refresh(monday)
    assert texts(monday) == ["Print 30 × Lyric sheet (Music/Y8/lyrics.pdf)"]  # ticked, so kept
    refresh(monday)
    assert monday.prep_items.count() == 1  # no duplicates


def test_tick_untick_add_and_remove(client, monday):
    refresh(monday)
    item = monday.prep_items.first()
    client.post(f"/sweep/prep/items/{item.pk}/toggle/")
    item.refresh_from_db()
    assert item.done_at is not None
    client.post(f"/sweep/prep/items/{item.pk}/toggle/")
    item.refresh_from_db()
    assert item.done_at is None
    client.post(f"/sweep/prep/{monday.pk}/add/", {"text": "  Tune the ukuleles  "})
    manual = monday.prep_items.get(source=PrepItem.MANUAL)
    assert manual.text == "Tune the ukuleles"
    client.post(f"/sweep/prep/items/{manual.pk}/remove/")
    assert not monday.prep_items.filter(source=PrepItem.MANUAL).exists()


def test_generated_items_cannot_be_removed_only_ticked(client, monday):
    refresh(monday)
    item = monday.prep_items.first()
    assert client.post(f"/sweep/prep/items/{item.pk}/remove/").status_code == 404
