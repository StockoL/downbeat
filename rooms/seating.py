"""
Seating plan changes. Every change returns a snapshot of the seats it touched, taken before
the change, so the caller can keep an undo stack. Restoring a snapshot reverses the change.
"""

import math

from django.db import transaction

from .models import SeatAssignment, SeatingPlan

UNDO_LIMIT = 10


class SeatLocked(Exception):
    pass


def snapshot(plan, seat_ids):
    """[[seat_id, pupil_id or None, locked], ...] for the given seats."""
    held = {a.seat_id: a for a in plan.assignments.filter(seat_id__in=seat_ids)}
    return [
        [str(seat_id), str(held[seat_id].pupil_id) if seat_id in held else None, held[seat_id].locked if seat_id in held else False]
        for seat_id in seat_ids
    ]


@transaction.atomic
def restore(plan, snap):
    seat_ids = [seat_id for seat_id, _, _ in snap]
    pupil_ids = [pupil_id for _, pupil_id, _ in snap if pupil_id]
    plan.assignments.filter(seat_id__in=seat_ids).delete()
    plan.assignments.filter(pupil_id__in=pupil_ids).delete()
    SeatAssignment.objects.bulk_create([
        SeatAssignment(seating_plan=plan, seat_id=seat_id, pupil_id=pupil_id, locked=locked)
        for seat_id, pupil_id, locked in snap if pupil_id
    ])


@transaction.atomic
def move(plan, pupil, seat):
    """
    Put a pupil in a seat. If someone is already there they swap, or go back to the
    unseated list when the moving pupil wasn't seated. Locked seats don't move.
    Returns the undo snapshot, or None if nothing changed.
    """
    current = plan.assignments.filter(pupil=pupil).first()
    occupant = plan.assignments.filter(seat=seat).first()
    if (current and current.locked) or (occupant and occupant.locked):
        raise SeatLocked
    if current and current.seat_id == seat.id:
        return None

    touched = [seat.id] + ([current.seat_id] if current else [])
    snap = snapshot(plan, touched)
    for assignment in (current, occupant):
        if assignment:
            assignment.delete()
    SeatAssignment.objects.create(seating_plan=plan, seat=seat, pupil=pupil)
    if current and occupant:
        SeatAssignment.objects.create(seating_plan=plan, seat_id=current.seat_id, pupil_id=occupant.pupil_id)
    return snap


@transaction.atomic
def unseat(plan, pupil):
    current = plan.assignments.filter(pupil=pupil).first()
    if current is None:
        return None
    if current.locked:
        raise SeatLocked
    snap = snapshot(plan, [current.seat_id])
    current.delete()
    return snap


@transaction.atomic
def toggle_lock(plan, seat):
    assignment = plan.assignments.filter(seat=seat).first()
    if assignment is None:
        return None
    snap = snapshot(plan, [seat.id])
    assignment.locked = not assignment.locked
    assignment.save(update_fields=["locked", "updated_at"])
    return snap


def _front_first(room):
    """Seats ordered from the teacher outwards, or top to bottom if the teacher isn't placed."""
    seats = list(room.seats.all())
    if room.teacher_x is None or room.teacher_y is None:
        return sorted(seats, key=lambda s: (s.y, s.x))
    return sorted(seats, key=lambda s: math.hypot(s.x - room.teacher_x, s.y - room.teacher_y))


@transaction.atomic
def create_plan(klass, room, date):
    """
    A new plan for this class in this room. If the class has a plan in another room, each
    pupil goes to a seat of the same zone here, keeping their order from the teacher outwards,
    so front stays front. Pupils with no matching seat are left unseated to tidy at the desk.
    Returns (plan, source plan or None).
    """
    source = SeatingPlan.objects.filter(klass=klass).exclude(room=room).first()
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=date)
    if source is None:
        return plan, None

    free = {}
    for seat in _front_first(room):
        free.setdefault(seat.zone, []).append(seat)
    by_seat = {a.seat_id: a for a in source.assignments.all()}
    members = set(klass.pupils.values_list("id", flat=True))
    new = []
    for seat in _front_first(source.room):
        assignment = by_seat.get(seat.id)
        if assignment is None or assignment.pupil_id not in members:
            continue
        matches = free.get(seat.zone)
        if matches:
            new.append(SeatAssignment(seating_plan=plan, seat=matches.pop(0), pupil_id=assignment.pupil_id))
    SeatAssignment.objects.bulk_create(new)
    return plan, source


def push_undo(session, plan, snap):
    if snap is None:
        return
    key = f"undo:{plan.pk}"
    stack = session.get(key, [])
    stack.append(snap)
    session[key] = stack[-UNDO_LIMIT:]


def pop_undo(session, plan):
    key = f"undo:{plan.pk}"
    stack = session.get(key, [])
    if not stack:
        return None
    snap = stack.pop()
    session[key] = stack
    return snap


def undo_count(session, plan):
    return len(session.get(f"undo:{plan.pk}", []))
