"""
Parents' evenings: slots made from the evening's times, booking from the class list or the school's
booking CSV, and the night itself. A family that doesn't come becomes an action in the class's
lessons, so the follow-up isn't left to memory.
"""

import csv
import datetime
import io

from django.db import IntegrityError, transaction
from django.utils import timezone

from notes.models import Note
from timetable.models import Pupil, Session

from .models import EveningSlot


class Refused(Exception):
    pass


def _minutes(t):
    return t.hour * 60 + t.minute


def _time(minutes):
    return datetime.time(minutes // 60, minutes % 60)


def _breaks(evening):
    spans = []
    for pair in evening.break_times or []:
        try:
            spans.append((_minutes(datetime.time.fromisoformat(pair[0])), _minutes(datetime.time.fromisoformat(pair[1]))))
        except (TypeError, ValueError, IndexError):
            continue
    return spans


def slot_times(evening):
    """Every start time from the evening's start, stepping by the slot length, that ends by the close and misses the breaks."""
    step = max(1, evening.slot_minutes)
    times, at, end = [], _minutes(evening.start), _minutes(evening.end)
    breaks = _breaks(evening)
    while at + step <= end:
        if not any(start < at + step and at < stop for start, stop in breaks):
            times.append(_time(at))
        at += step
    return times


@transaction.atomic
def generate_slots(evening):
    """Adds the slots the times call for and removes free ones they no longer do. A booked slot is never removed."""
    wanted = set(slot_times(evening))
    have = {s.start_time: s for s in evening.slots.all()}
    EveningSlot.objects.bulk_create([EveningSlot(evening=evening, start_time=t) for t in sorted(wanted - set(have))])
    stale = [s.pk for t, s in have.items() if t not in wanted and s.pupil_id is None]
    EveningSlot.objects.filter(pk__in=stale).delete()
    return len(wanted - set(have))


def book(slot, pupil):
    if slot.pupil_id and slot.pupil_id != pupil.pk:
        raise Refused(f"{slot.start_time:%H:%M} is already booked for {slot.pupil}.")
    if EveningSlot.objects.filter(evening=slot.evening, pupil=pupil).exclude(pk=slot.pk).exists():
        raise Refused(f"{pupil}'s family already has a time this evening.")
    slot.pupil, slot.booked_at = pupil, timezone.now()
    try:
        slot.save(update_fields=["pupil", "booked_at", "updated_at"])
    except IntegrityError as error:
        raise Refused(f"{pupil}'s family already has a time this evening.") from error


def unbook(slot):
    slot.pupil, slot.booked_at, slot.attended = None, None, None
    slot.save(update_fields=["pupil", "booked_at", "attended", "updated_at"])


def _find_pupil(name):
    """'Ada M' or 'Ada Mistry' (cut to the initial, as class lists are): one match, or None."""
    parts = name.split()
    if len(parts) < 2:
        return None
    matches = list(Pupil.objects.filter(first_name__iexact=" ".join(parts[:-1]), surname_initial__iexact=parts[-1][0]))
    return matches[0] if len(matches) == 1 else None


@transaction.atomic
def import_bookings(evening, text):
    """
    Rows of time and pupil name ("17:05, Ada Mistry"), from the school's booking system. Returns
    (booked, problems): each problem names its row, so the teacher can book those by hand.
    """
    slots = {s.start_time: s for s in evening.slots.all()}
    booked, problems = 0, []
    for number, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        cells = [c.strip() for c in row if c.strip()]
        if len(cells) < 2:
            continue
        try:
            when = datetime.time.fromisoformat(cells[0].replace(".", ":"))
        except ValueError:
            if number == 1:
                continue  # a header row
            problems.append(f"Row {number}: “{cells[0]}” isn't a time.")
            continue
        pupil = _find_pupil(cells[1])
        if when not in slots:
            problems.append(f"Row {number}: there is no {when:%H:%M} slot this evening.")
        elif pupil is None:
            problems.append(f"Row {number}: no single pupil matches “{cells[1]}”.")
        else:
            try:
                book(slots[when], pupil)
                booked += 1
            except Refused as error:
                problems.append(f"Row {number}: {error}")
    return booked, problems


def mark(slot, attended):
    """
    Attended or not. A family that didn't come becomes an open action, "Follow up with parents", on the
    pupil's latest lesson by the evening, so it is in the Actions sheet of their next lesson. Once.
    """
    first_miss = attended is False and slot.attended is not False
    slot.attended = attended
    slot.save(update_fields=["attended", "updated_at"])
    if not first_miss or slot.pupil_id is None:
        return None
    lesson = (Session.objects.filter(klass__pupils=slot.pupil_id, date__lte=slot.evening.date).exclude(status=Session.CANCELLED)
              .order_by("-date", "-period").first())
    if lesson is None:
        return None
    note = Note.objects.create(session=lesson, pupil_id=slot.pupil_id, actionable=True,
                               text=f"Follow up with parents: missed {slot.evening}")
    slot.follow_up_note = note.text
    slot.save(update_fields=["follow_up_note", "updated_at"])
    return note
