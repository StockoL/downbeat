import datetime

import pytest
from django.utils import timezone

from notes.models import Note, NoteType, SpokenTo
from pupils.missing_out import missing_out, window_start
from timetable.models import Class, Session, SessionAttendance

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 11, 2)


@pytest.fixture
def week(timetable, klass, room, pupils):
    hp = NoteType.objects.create(label="House point", is_house_point=True)
    other = NoteType.objects.create(label="Great answer")
    lessons = [Session.objects.create(date=D + datetime.timedelta(days=d), period="P1", klass=klass, room=room) for d in range(3)]
    # Aleya: 2 house points; Jojo: 1 house point, 2 turns; Sam: none, 1 turn, absent once.
    Note.objects.create(session=lessons[0], pupil=pupils[0], note_type=hp)
    Note.objects.create(session=lessons[1], pupil=pupils[0], note_type=hp)
    Note.objects.create(session=lessons[1], pupil=pupils[1], note_type=hp)
    Note.objects.create(session=lessons[1], pupil=pupils[2], note_type=other)  # not a house point
    Note.objects.create(session=lessons[2], pupil=pupils[2], note_type=hp, deleted_at=timezone.now())  # removed
    SpokenTo.objects.create(session=lessons[0], pupil=pupils[1])
    SpokenTo.objects.create(session=lessons[2], pupil=pupils[1])
    SpokenTo.objects.create(session=lessons[2], pupil=pupils[2])
    SessionAttendance.objects.create(session=lessons[0], pupil=pupils[2], present=False)
    elsewhere = Session.objects.create(date=D, period="P2", klass=Class.objects.create(name="Choir"), room=room)
    Note.objects.create(session=elsewhere, pupil=pupils[2], note_type=hp)  # another class: not counted
    return lessons


def test_fewest_house_points_then_fewest_turns_first(week, klass, pupils):
    rows = missing_out(klass, D)
    assert [(str(r["pupil"]), r["house_points"], r["spoken"], r["absences"]) for r in rows] == [
        ("Sam T", 0, 1, 1), ("Jojo P", 1, 2, 0), ("Aleya K", 2, 0, 0),
    ]


def test_counts_only_from_the_start_date(week, klass, pupils):
    rows = {str(r["pupil"]): r for r in missing_out(klass, D + datetime.timedelta(days=1))}
    assert rows["Aleya K"]["house_points"] == 1 and rows["Jojo P"]["spoken"] == 1


def test_window_starts_at_the_term_or_seven_weeks_back(klass):
    today = datetime.date(2026, 11, 20)
    assert window_start(klass, today) == today - datetime.timedelta(weeks=7)
    klass.term_start = datetime.date(2026, 11, 2)
    assert window_start(klass, today) == datetime.date(2026, 11, 2)


def test_missing_out_page(client, week, klass):
    html = client.get(f"/pupils/class/{klass.pk}/missing-out/?since=2026-11-02").content.decode()
    assert html.index("Sam T") < html.index("Jojo P") < html.index("Aleya K")
    assert client.get(f"/pupils/class/{klass.pk}/missing-out/?since=nonsense").status_code == 200
