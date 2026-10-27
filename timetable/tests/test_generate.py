import datetime

import pytest
from django.core.management import call_command

from timetable.models import Session, Slot
from timetable.services import generate_sessions, week_letter

pytestmark = pytest.mark.django_db

MON = datetime.date(2026, 11, 2)


def test_week_letter_alternates_from_the_start_week():
    assert week_letter(MON, MON, "A") == "A"
    assert week_letter(MON + datetime.timedelta(days=4), MON, "A") == "A"
    assert week_letter(MON + datetime.timedelta(days=7), MON, "A") == "B"
    assert week_letter(MON + datetime.timedelta(days=14), MON, "A") == "A"
    # starting midweek still counts from that week's Monday
    assert week_letter(MON + datetime.timedelta(days=7), MON + datetime.timedelta(days=3), "B") == "A"


def test_two_week_cycle_places_week_b_slots_in_alternate_weeks(timetable, room, klass):
    Slot.objects.create(timetable=timetable, week="B", day=2, period="P2", room=room, klass=klass)
    created = generate_sessions(timetable, MON, MON + datetime.timedelta(days=27), "A")
    assert created == 2
    assert sorted(Session.objects.values_list("date", flat=True)) == [
        datetime.date(2026, 11, 11), datetime.date(2026, 11, 25),
    ]
    session = Session.objects.first()
    assert (session.period, session.room, session.klass) == ("P2", room, klass)


def test_one_week_cycle_repeats_every_week(timetable, room, klass):
    timetable.week_cycle = 1
    timetable.save()
    Slot.objects.create(timetable=timetable, week="A", day=0, period="P1", room=room, klass=klass)
    assert generate_sessions(timetable, MON, MON + datetime.timedelta(days=20)) == 3


def test_generating_twice_keeps_per_day_edits(timetable, room, klass):
    from rooms.models import Room
    Slot.objects.create(timetable=timetable, week="A", day=0, period="P1", room=room, klass=klass)
    generate_sessions(timetable, MON, MON, "A")
    moved = Room.objects.create(name="Hall")
    Session.objects.update(room=moved, status=Session.MOVED)
    assert generate_sessions(timetable, MON, MON, "A") == 0
    assert Session.objects.get().room == moved


def test_management_command(timetable, room, klass, capsys):
    Slot.objects.create(timetable=timetable, week="A", day=0, period="P1", room=room, klass=klass)
    call_command("generate_sessions", "2026-11-02", "2026-11-13", "--first-week", "A")
    assert "Created 1 session." in capsys.readouterr().out
    assert Session.objects.get().date == MON
