import datetime

from .models import Session, Slot


def week_letter(date, start, first_week):
    """A or B for a date, counting whole weeks from the Monday of `start`, which is `first_week`."""
    first_monday = start - datetime.timedelta(days=start.weekday())
    weeks_on = (date - first_monday).days // 7
    if weeks_on % 2 == 0:
        return first_week
    return "B" if first_week == "A" else "A"


def generate_sessions(timetable, start, end, first_week="A"):
    """
    Create a Session for every slot that falls between start and end inclusive.
    Days that already have a session for a slot are left alone, so running it twice is safe
    and per-day edits (a moved room, a cancellation) survive.
    Returns the number of sessions created.
    """
    slots = list(Slot.objects.filter(timetable=timetable))
    existing = set(
        Session.objects.filter(date__range=(start, end), slot__in=slots).values_list("date", "slot_id")
    )
    new = []
    date = start
    while date <= end:
        if date.weekday() < 5:
            week = week_letter(date, start, first_week) if timetable.week_cycle == 2 else "A"
            for slot in slots:
                if slot.day == date.weekday() and slot.week == week and (date, slot.id) not in existing:
                    new.append(Session(date=date, slot=slot, period=slot.period, room_id=slot.room_id, klass_id=slot.klass_id))
        date += datetime.timedelta(days=1)
    Session.objects.bulk_create(new)
    return len(new)
