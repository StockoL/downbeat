"""Instrumental rotations: building the grid, reading it from a spreadsheet, and who is out when."""

import datetime
import re

from .models import PupilRotation

DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri"]


class BadSchedule(ValueError):
    pass


def monday_of(date):
    return date - datetime.timedelta(days=date.weekday())


def rotating(day, periods, first_week, weeks):
    """
    The usual peripatetic pattern: one day, the slots stepping one period later each week, so a
    pupil doesn't miss the same lesson every time. Returns (weeks, slots) for a Rotation.
    """
    first = monday_of(first_week)
    week_list, slots = [], []
    n = len(periods)
    for w in range(weeks):
        week_list.append((first + datetime.timedelta(weeks=w)).isoformat())
        slots.append([[day, periods[(i + w) % n]] for i in range(n)])
    return week_list, slots


def parse_schedule(text, known_periods):
    """
    One row per week, as pasted from the department's spreadsheet:
        02/11/2026, Tue P1, Tue P2, Tue P3
    Commas or tabs between cells; a header row without a date is skipped. Every row needs the
    same number of slots. Returns (weeks, slots).
    """
    weeks, slots = [], []
    for number, line in enumerate(text.splitlines(), start=1):
        cells = [c.strip() for c in re.split(r"[,\t]", line) if c.strip()]
        if not cells:
            continue
        date = _parse_date(cells[0])
        if date is None:
            if not weeks:
                continue  # a header row
            raise BadSchedule(f"Row {number}: the first cell should be a date, like 02/11/2026.")
        row = []
        for cell in cells[1:]:
            parts = cell.split(None, 1)
            if len(parts) != 2 or parts[0][:3].lower() not in DAYS:
                raise BadSchedule(f"Row {number}: '{cell}' should be a day and a period, like Tue P1.")
            if parts[1] not in known_periods:
                raise BadSchedule(f"Row {number}: '{parts[1]}' isn't a period in the timetable.")
            row.append([DAYS[parts[0][:3].lower()], parts[1]])
        if not row:
            raise BadSchedule(f"Row {number}: no slots after the date.")
        if slots and len(row) != len(slots[0]):
            raise BadSchedule(f"Row {number}: {len(row)} slots, but the first week has {len(slots[0])}.")
        weeks.append(monday_of(date).isoformat())
        slots.append(row)
    if not weeks:
        raise BadSchedule("No weeks found. Each row starts with a date.")
    return weeks, slots


def _parse_date(text):
    for pattern in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def out_of(session):
    """Pupils of this lesson's class who are at an instrumental lesson during it."""
    week = monday_of(session.date)
    day = session.date.weekday()
    out = set()
    for entry in PupilRotation.objects.filter(pupil__classes=session.klass).select_related("rotation"):
        if entry.rotation.when(week, entry.slot_index) == (day, session.period):
            out.add(entry.pupil_id)
    return out


def describe(day, period):
    return f"{DAY_NAMES[day]} {period}"
