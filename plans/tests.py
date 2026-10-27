import datetime

import pytest
from django.utils import timezone

from plans.models import LessonPlan, PlanActivity, Resource, Scheme, Unit
from plans.services import fill_from_unit
from timetable.models import Session

pytestmark = pytest.mark.django_db


@pytest.fixture
def blues(db):
    scheme = Scheme.objects.create(name="Year 8", year_group=8)
    unit = Unit.objects.create(scheme=scheme, name="Blues", order=1, lessons_planned=3)
    for n in range(1, 4):
        lesson = LessonPlan.objects.create(unit=unit, order=n, objective=f"Blues lesson {n}")
        PlanActivity.objects.create(lesson_plan=lesson, order=0, text="Warm-up", minutes=5)
        PlanActivity.objects.create(lesson_plan=lesson, order=1, text="Riff in pairs", minutes=20)
        Resource.objects.create(lesson_plan=lesson, title="Lyric sheet", needs_print=True, copies=30)
    return unit


def formset(prefix, rows, initial=0):
    data = {f"{prefix}-TOTAL_FORMS": str(len(rows)), f"{prefix}-INITIAL_FORMS": str(initial),
            f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"}
    for i, row in enumerate(rows):
        data.update({f"{prefix}-{i}-{k}": v for k, v in row.items()})
    return data


# --- Schemes, units, lessons ---

def test_pages_render(client, timetable, klass, blues):
    lesson = blues.lessons.first()
    for url in ["/plan/", "/plan/schemes/", f"/plan/schemes/{blues.scheme.pk}/", f"/plan/units/{blues.pk}/",
                f"/plan/lessons/{lesson.pk}/", f"/plan/classes/{klass.pk}/"]:
        assert client.get(url).status_code == 200, url


def test_create_a_scheme_and_a_unit(client, timetable):
    response = client.post("/plan/schemes/", {"name": "Year 7", "year_group": "7"})
    scheme = Scheme.objects.get()
    assert response.url == f"/plan/schemes/{scheme.pk}/"
    client.post(f"/plan/schemes/{scheme.pk}/", {"name": "Samba", "order": "1", "lessons_planned": "6"})
    assert scheme.units.get().name == "Samba"


def test_add_a_lesson_then_write_it(client, timetable, blues):
    response = client.post(f"/plan/units/{blues.pk}/lessons/")
    lesson = LessonPlan.objects.get(unit=blues, order=4)
    assert response.url == f"/plan/lessons/{lesson.pk}/"
    data = {"order": "4", "objective": "Write a twelve-bar", "main": "Compose in pairs"}
    data |= formset("activities", [{"order": "0", "text": "Listen", "minutes": "10"}, {"order": "1", "text": "Compose", "minutes": "30"}])
    data |= formset("resources", [{"title": "Chord chart", "path_or_url": "Music/Y8/Blues/chords.pdf", "needs_print": "on", "copies": "15"}])
    client.post(f"/plan/lessons/{lesson.pk}/", data)
    lesson.refresh_from_db()
    assert lesson.objective == "Write a twelve-bar"
    assert [(a.text, a.minutes) for a in lesson.activities.all()] == [("Listen", 10), ("Compose", 30)]
    assert lesson.resources.get().copies == 15


def test_duplicate_a_unit_copies_everything_and_leaves_the_original(client, timetable, blues):
    response = client.post(f"/plan/units/{blues.pk}/duplicate/")
    copy = Unit.objects.exclude(pk=blues.pk).get()
    assert response.url == f"/plan/units/{copy.pk}/"
    assert copy.name == "Blues (copy)" and copy.lessons.count() == 3
    assert PlanActivity.objects.filter(lesson_plan__unit=copy).count() == 6
    assert Resource.objects.filter(lesson_plan__unit=copy, needs_print=True).count() == 3
    assert blues.lessons.count() == 3


def test_deleting_a_unit_keeps_the_sessions(client, timetable, klass, room, blues):
    session = Session.objects.create(date=timezone.localdate(), period="P1", klass=klass, room=room, lesson=blues.lessons.first())
    client.post(f"/plan/units/{blues.pk}/delete/")
    session.refresh_from_db()
    assert not Unit.objects.exists() and session.lesson is None


# --- Sessions and lessons ---

def week_of_sessions(klass, room, start, count):
    return [Session.objects.create(date=start + datetime.timedelta(days=i), period="P1", klass=klass, room=room) for i in range(count)]


def test_fill_carries_on_after_the_last_lesson_taught(timetable, klass, room, blues):
    today = timezone.localdate()
    taught = Session.objects.create(date=today - datetime.timedelta(days=2), period="P1", klass=klass, room=room,
                                    lesson=blues.lessons.get(order=1), status=Session.TAUGHT)
    coming = week_of_sessions(klass, room, today, 4)
    assert fill_from_unit(klass, blues) == 2  # lessons 2 and 3; the fourth session stays free
    lessons = [Session.objects.get(pk=s.pk).lesson for s in coming]
    assert [lesson.order if lesson else None for lesson in lessons] == [2, 3, None, None]
    assert taught.lesson.order == 1


def test_fill_skips_sessions_that_already_have_a_lesson(client, timetable, klass, room, blues):
    today = timezone.localdate()
    first, second = week_of_sessions(klass, room, today, 2)
    first.lesson = blues.lessons.get(order=3)
    first.save()
    client.post(f"/plan/classes/{klass.pk}/fill/", {"unit": blues.pk})
    second.refresh_from_db()
    assert second.lesson is None  # lesson 3 was the last; nothing after it


def test_set_and_clear_a_sessions_lesson(client, timetable, klass, room, blues):
    session = Session.objects.create(date=timezone.localdate(), period="P1", klass=klass, room=room)
    lesson = blues.lessons.get(order=2)
    client.post(f"/plan/sessions/{session.pk}/lesson/", {"lesson": lesson.pk})
    session.refresh_from_db()
    assert session.lesson == lesson
    client.post(f"/plan/sessions/{session.pk}/lesson/", {"lesson": ""})
    session.refresh_from_db()
    assert session.lesson is None
