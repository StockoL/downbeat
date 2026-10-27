"""
Seating plan changes. Every change returns a snapshot of the seats it touched, taken before
the change, so the caller can keep an undo stack. Restoring a snapshot reverses the change.
"""

import datetime
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


def seating_for(session):
    """(plan or None, {seat_id: pupil}, [unseated pupils]) for a session's class in its room."""
    plan = SeatingPlan.current(session.klass, session.room, session.date)
    seated = {a.seat_id: a.pupil for a in plan.assignments.select_related("pupil")} if plan else {}
    seated_ids = {p.pk for p in seated.values()}
    unseated = [p for p in session.klass.pupils.all() if p.pk not in seated_ids]
    return plan, seated, unseated


def build_problem(plan):
    """The shuffle's inputs for a plan: its room, its class, their locks, relationships and flag rules."""
    from pupils.services import placement_rules, relationships_among

    from .adjacency import meets_rule, neighbours
    from .solver import Problem

    seats = list(plan.room.seats.all())
    pupils = list(plan.klass.pupils.values_list("id", flat=True))
    pairs = relationships_among(pupils)
    rules = placement_rules(pupils)
    return Problem(
        seats=[s.id for s in seats],
        pupils=pupils,
        neighbours=neighbours(seats),
        locked={a.seat_id: a.pupil_id for a in plan.assignments.filter(locked=True, pupil_id__in=pupils)},
        keep_apart={frozenset((a, b)) for a, b, kind in pairs if kind == "keep_apart"},
        pair_well={frozenset((a, b)) for a, b, kind in pairs if kind == "pair_well"},
        rules_met={
            pupil: {s.id for s in seats if all(meets_rule(rule, s, plan.room) for rule in pupil_rules)}
            for pupil, pupil_rules in rules.items()
        },
    )


@transaction.atomic
def shuffle_plan(plan, rng=None):
    """
    Reseat the class: locked seats stay, keep-apart pairs end up apart, rules and pairs are met
    where possible. Returns the undo snapshot of every seat. Raises solver.NoArrangement.
    """
    from .solver import shuffle

    arrangement = shuffle(build_problem(plan), rng)
    seat_ids = list(plan.room.seats.values_list("id", flat=True))
    snap = snapshot(plan, seat_ids)
    plan.assignments.filter(locked=False).delete()
    locked = set(plan.assignments.values_list("seat_id", flat=True))
    SeatAssignment.objects.bulk_create([
        SeatAssignment(seating_plan=plan, seat_id=seat, pupil_id=pupil)
        for seat, pupil in arrangement.items() if seat not in locked
    ])
    return snap


@transaction.atomic
def duplicate_plan(plan, date):
    """A copy that takes over from `date`; the original ends the day before and stays as history."""
    copy = SeatingPlan.objects.create(klass=plan.klass, room=plan.room, name=plan.name, active_from=date)
    SeatAssignment.objects.bulk_create([
        SeatAssignment(seating_plan=copy, seat_id=a.seat_id, pupil_id=a.pupil_id, locked=a.locked)
        for a in plan.assignments.all()
    ])
    if plan.active_from < date:
        plan.active_to = date - datetime.timedelta(days=1)
        plan.save(update_fields=["active_to", "updated_at"])
    return copy
