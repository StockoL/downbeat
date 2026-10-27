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


def period_order(timetable):
    return {p["label"]: i for i, p in enumerate(timetable.periods)}


def sessions_on(date, timetable):
    """A day's sessions in timetable order, each with .start and .end from its period."""
    order = period_order(timetable)
    sessions = sorted(
        Session.objects.filter(date=date).select_related("klass", "room"),
        key=lambda s: (order.get(s.period, len(order)), s.period),
    )
    for session in sessions:
        session.start, session.end = timetable.period_times(session.period)
    return sessions


def live_session(now, timetable):
    """The session happening at this moment, if any. Cancelled sessions are never live."""
    for session in sessions_on(now.date(), timetable):
        if session.status != Session.CANCELLED and session.start and session.start <= now.time() < session.end:
            return session
    return None


def next_session(session, timetable, horizon_days=60):
    """The next session after this one that isn't cancelled: later today, or on a later day."""
    order = period_order(timetable)
    rank = lambda s: (s.date, order.get(s.period, len(order)), s.period)
    later = Session.objects.filter(
        date__gte=session.date, date__lte=session.date + datetime.timedelta(days=horizon_days),
    ).exclude(status=Session.CANCELLED).exclude(pk=session.pk).select_related("klass", "room")
    candidates = sorted((s for s in later if rank(s) > rank(session)), key=rank)
    return candidates[0] if candidates else None


def previous_session(session, timetable, horizon_days=60):
    """The last session with the same class before this one that wasn't cancelled."""
    order = period_order(timetable)
    rank = lambda s: (s.date, order.get(s.period, len(order)), s.period)
    earlier = Session.objects.filter(
        klass_id=session.klass_id, date__lte=session.date,
        date__gte=session.date - datetime.timedelta(days=horizon_days),
    ).exclude(status=Session.CANCELLED).exclude(pk=session.pk)
    candidates = sorted((s for s in earlier if rank(s) < rank(session)), key=rank)
    return candidates[-1] if candidates else None
