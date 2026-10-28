"""
Applying operations queued on a device. Every capture made in the room view arrives here as an
operation with an id made on the device, so the iPad can record a lesson with no connection and
send it later. Applying is idempotent and last-write-wins, so sending the same queue twice, or
resending after a dropped connection, changes nothing.

    note.add        {id, session, pupil|group, note_type|null, text, actionable, at}
    note.remove     {note, at}
    note.restore    {note, at}
    action.done     {note, at}
    spoken.add      {id, session, pupil, at}
    spoken.remove   {spoken, at}
    spoken.clear    {session, pupil, at}
    attendance.set  {session, pupil, present, at}
    checklist.tick  {id, session, item, at}
    checklist.untick {session, item, at}
    observation.add {id, session, pupil, component, state, next_step, at}
    observation.update {observation, next_step, at}
    observation.remove {observation, at}
    check.decide    {id, session, check, decision, at}
    check.clear     {check, at}
"""

import datetime
import uuid

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from assessment.models import Check, Component, Observation
from pupils.models import Group
from timetable.models import Pupil, Session, SessionAttendance, Timetable

from .models import ChecklistItem, ChecklistTick, Note, NoteType, SpokenTo


class Rejected(Exception):
    """An operation that can never apply, e.g. its lesson was deleted. Dropped from the queue."""


def _at(op):
    at = parse_datetime(str(op.get("at", "")))
    if at is None:
        raise Rejected("missing or unreadable time")
    if timezone.is_naive(at):
        at = timezone.make_aware(at, datetime.UTC)
    # A device clock far in the future would win every later edit; hold it to now.
    return min(at, timezone.now() + datetime.timedelta(minutes=5))


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except ValueError as error:
        raise Rejected("bad id") from error


def _get(model, pk):
    try:
        row = model.objects.get(pk=_uuid(pk))
    except model.DoesNotExist as error:
        raise Rejected(f"no such {model._meta.model_name}") from error
    session = row if isinstance(row, Session) else getattr(row, "session", None)
    if session is not None and session.klass.archived_on:
        raise Rejected("that class is archived, so its lessons are read-only")
    return row


def _newer(note, at):
    """Last write wins: only apply a change made after the note was last changed."""
    return at >= note.updated_at


def note_add(op):
    note_id = _uuid(op.get("id"))
    if Note.objects.filter(pk=note_id).exists():
        return  # already applied
    session = _get(Session, op.get("session"))
    pupil = _get(Pupil, op["pupil"]) if op.get("pupil") else None
    group = _get(Group, op["group"]) if op.get("group") else None
    if (pupil is None) == (group is None):
        raise Rejected("a note is for one pupil or one group")
    if group is not None and group.klass_id != session.klass_id:
        raise Rejected("that group isn't in this lesson's class")
    note_type = _get(NoteType, op["note_type"]) if op.get("note_type") else None
    text = str(op.get("text", "")).strip()[:2000]
    if note_type is None and not text:
        raise Rejected("an empty free-text note")
    actionable = bool(op.get("actionable")) if note_type is None else note_type.is_actionable_default
    at = _at(op)
    Note.objects.create(
        id=note_id, session=session, pupil=pupil, group=group, note_type=note_type, text=text, actionable=actionable,
    )
    Note.objects.filter(pk=note_id).update(created_at=at, updated_at=at)  # the time it was caught, not sent


def note_remove(op):
    note, at = _get(Note, op.get("note")), _at(op)
    if _newer(note, at):
        Note.objects.filter(pk=note.pk).update(deleted_at=at, updated_at=at)


def note_restore(op):
    note, at = _get(Note, op.get("note")), _at(op)
    if _newer(note, at):
        Note.objects.filter(pk=note.pk).update(deleted_at=None, updated_at=at)


def action_done(op):
    note, at = _get(Note, op.get("note")), _at(op)
    if note.done_at is None:
        Note.objects.filter(pk=note.pk).update(done_at=at, updated_at=max(at, note.updated_at))


def spoken_add(op):
    spoken_id = _uuid(op.get("id"))
    if SpokenTo.objects.filter(pk=spoken_id).exists():
        return
    session, pupil, at = _get(Session, op.get("session")), _get(Pupil, op.get("pupil")), _at(op)
    SpokenTo.objects.create(id=spoken_id, session=session, pupil=pupil)
    SpokenTo.objects.filter(pk=spoken_id).update(created_at=at, updated_at=at)


def spoken_remove(op):
    SpokenTo.objects.filter(pk=_uuid(op.get("spoken"))).delete()


def spoken_clear(op):
    """Toggle off: every row for this pupil this lesson made before the tap."""
    session, pupil, at = _get(Session, op.get("session")), _get(Pupil, op.get("pupil")), _at(op)
    SpokenTo.objects.filter(session=session, pupil=pupil, created_at__lte=at).delete()


def attendance_set(op):
    session, pupil, at = _get(Session, op.get("session")), _get(Pupil, op.get("pupil")), _at(op)
    row, created = SessionAttendance.objects.get_or_create(session=session, pupil=pupil)
    if created or at >= row.updated_at:
        SessionAttendance.objects.filter(pk=row.pk).update(present=bool(op.get("present")), updated_at=at)


def checklist_tick(op):
    tick_id = _uuid(op.get("id"))
    if ChecklistTick.objects.filter(pk=tick_id).exists():
        return
    session, item, at = _get(Session, op.get("session")), _get(ChecklistItem, op.get("item")), _at(op)
    if item.klass_id and item.klass_id != session.klass_id:
        raise Rejected("that checklist item belongs to another class")
    ChecklistTick.objects.create(id=tick_id, session=session, checklist_item=item, ticked_at=at)


def checklist_untick(op):
    session, item, at = _get(Session, op.get("session")), _get(ChecklistItem, op.get("item")), _at(op)
    ChecklistTick.objects.filter(session=session, checklist_item=item, ticked_at__lte=at).delete()


def observation_add(op):
    observation_id = _uuid(op.get("id"))
    if Observation.objects.filter(pk=observation_id).exists():
        return
    session, pupil, component = _get(Session, op.get("session")), _get(Pupil, op.get("pupil")), _get(Component, op.get("component"))
    state = op.get("state")
    if state not in dict(Observation.STATES):
        raise Rejected("unknown state")
    next_step = str(op.get("next_step") or "").strip()[:200]
    if not next_step:
        raise Rejected("an observation needs a next step")
    at = _at(op)
    Observation.objects.create(id=observation_id, session=session, pupil=pupil, component=component, state=state, next_step=next_step)
    Observation.objects.filter(pk=observation_id).update(created_at=at, updated_at=at)


def observation_update(op):
    observation, at = _get(Observation, op.get("observation")), _at(op)
    next_step = str(op.get("next_step") or "").strip()[:200]
    if not next_step and not observation.recording_path:
        raise Rejected("an observation needs a next step")
    if at >= observation.updated_at:
        Observation.objects.filter(pk=observation.pk).update(next_step=next_step, updated_at=at)


def observation_remove(op):
    observation, at = _get(Observation, op.get("observation")), _at(op)
    if at >= observation.updated_at:
        Observation.objects.filter(pk=observation.pk).update(deleted_at=at, updated_at=at)


def _minutes_in(session, at):
    """How far into the period a decision was made; None if the period has no times or it was another day."""
    start, _ = Timetable.active().period_times(session.period)
    if start is None:
        return None
    minutes = (at - timezone.make_aware(datetime.datetime.combine(session.date, start))).total_seconds() // 60
    return max(0, int(minutes)) if minutes <= 600 else None


def check_decide(op):
    """
    The hinge decision. The first one copies the planned question into the session; a later one,
    from this device or another, changes the decision if it was made later.
    """
    decision = op.get("decision")
    if decision not in dict(Check.DECISIONS):
        raise Rejected("unknown decision")
    at = _at(op)
    row = Check.objects.filter(pk=_uuid(op.get("id"))).first()
    if row is None:
        session, source = _get(Session, op.get("session")), _get(Check, op.get("check"))
        if source.lesson_plan_id is None:
            raise Rejected("only a planned check can be asked")
        row = Check.objects.filter(session=session, source=source).first()
        if row is None:
            row = source.ask_in(session, id=_uuid(op.get("id")), decision=decision, minutes_in=_minutes_in(session, at))
            Check.objects.filter(pk=row.pk).update(created_at=at, updated_at=at)
            return
    if at >= row.updated_at:
        Check.objects.filter(pk=row.pk).update(decision=decision, updated_at=at)


def check_clear(op):
    """Takes a decision back. The row stays, blank, so a late resend of the decision can't revive it."""
    row, at = _get(Check, op.get("check")), _at(op)
    if row.session_id is None:
        raise Rejected("a planned check has no decision")
    if at >= row.updated_at:
        Check.objects.filter(pk=row.pk).update(decision="", updated_at=at)


HANDLERS = {
    "note.add": note_add,
    "note.remove": note_remove,
    "note.restore": note_restore,
    "action.done": action_done,
    "spoken.add": spoken_add,
    "spoken.remove": spoken_remove,
    "spoken.clear": spoken_clear,
    "attendance.set": attendance_set,
    "checklist.tick": checklist_tick,
    "checklist.untick": checklist_untick,
    "observation.add": observation_add,
    "observation.update": observation_update,
    "observation.remove": observation_remove,
    "check.decide": check_decide,
    "check.clear": check_clear,
}


def apply(ops):
    """
    Apply operations in the order they were made. Returns (applied, rejected): op ids that are
    done with (applied now or earlier) and those that can never apply, with a reason. Both lists
    are safe for the device to drop from its queue.
    """
    applied, rejected = [], []
    for op in ops:
        op_id = str(op.get("op_id", ""))
        handler = HANDLERS.get(op.get("type"))
        try:
            if handler is None:
                raise Rejected(f"unknown operation {op.get('type')!r}")
            with transaction.atomic():
                handler(op)
            applied.append(op_id)
        except Rejected as error:
            rejected.append({"op_id": op_id, "reason": str(error)})
    return applied, rejected
