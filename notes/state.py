"""
A lesson's state as plain data: what the room view draws its sheets, log, seat marks, actions
and picker from. The page holds it, applies the device's unsent operations on top, and fetches
it again after each successful sync, so the laptop stays the source of truth.
"""

import datetime
from collections import Counter

from django.utils import timezone

from pupils.services import active_groups
from rooms.seating import seating_for
from timetable.rotations import out_of

from . import goals, services
from .models import Note


def lesson_state(session):
    _, seated, unseated = seating_for(session)
    pupils = list(seated.values()) + unseated
    pupil_ids = [p.pk for p in pupils]
    actions = services.actions(session)
    in_class = Counter(n.pupil_id for n in actions if n.pupil_id)
    totals = Counter(
        Note.objects.open_actions().filter(pupil_id__in=pupil_ids).values_list("pupil_id", flat=True)
    )

    ticked = {}
    for tick in session.checklist_ticks.order_by("ticked_at"):
        ticked.setdefault(str(tick.checklist_item_id), []).append(str(tick.pk))

    spoken = {}
    for row in session.spoken_to.order_by("created_at"):
        spoken.setdefault(str(row.pupil_id), []).append(str(row.pk))

    def when(note):
        if note.session_id == session.pk:
            return "Today"
        return f"{note.session.date.day} {note.session.date:%b}"

    return {
        "session": str(session.pk),
        "noteTypes": [
            {"id": str(t.pk), "label": t.label, "icon": t.icon, "actionable": t.is_actionable_default}
            for t in services.sheet_types()
        ],
        "pupils": [{"id": str(p.pk), "name": str(p)} for p in pupils],
        "groups": [{"id": str(g.pk), "name": g.name} for g in active_groups(session.klass)],
        "notes": [_note(n) for n in services.log(session)],
        "actions": [{**_note(n), "when": when(n)} for n in actions],
        # Open actions for each pupil from other classes, so the unread counter covers them too.
        "elsewhere": {str(pk): totals[pk] - in_class[pk] for pk in pupil_ids if totals[pk] > in_class[pk]},
        "spoken": spoken,
        "absent": [str(pk) for pk in services.absent(session)],
        "present": [str(pk) for pk in session.attendance.filter(present=True).values_list("pupil_id", flat=True)],
        "register": session.klass.kind == "co_curricular",
        # Each goal's count from the other lessons in its window; the page adds this one.
        "goals": [
            {
                "id": str(g.pk), "label": g.text, "icon": g.counts_note_type.icon or g.counts_note_type.label[:2],
                "noteType": str(g.counts_note_type_id), "others": goals.tally(g, session.date, exclude=session),
                "target": g.target_count,
            }
            for g in goals.goals_for(session)
        ],
        "checklist": [{"id": str(item.pk), "text": item.text} for item in goals.checklist_items(session)],
        "ticked": ticked,
        "missed": [str(pk) for pk in services.missed_last_time(session)],
        "out": [str(pk) for pk in out_of(session)],
        "plan": _plan(session),
        # The unit's components for the observation sheet, and this lesson's observations.
        "components": [
            {"id": str(c.pk), "text": c.text, "nextStep": c.next_step_default}
            for c in (session.lesson.unit.components.all() if session.lesson_id else [])
        ],
        "observations": [
            {"id": str(o.pk), "pupil": str(o.pupil_id), "component": str(o.component_id), "state": o.state,
             "nextStep": o.next_step, "at": o.created_at.isoformat()}
            for o in session.observations.filter(deleted_at__isnull=True)
        ],
        # The lesson's hinge check, and what was decided (a blank decision was taken back).
        "hinge": _hinge(session),
        "decisions": [
            {"id": str(c.pk), "source": str(c.source_id) if c.source_id else None, "decision": c.decision,
             "minutesIn": c.minutes_in, "at": c.updated_at.isoformat()}
            for c in session.checks.all()
        ],
    }


def _hinge(session):
    check = session.lesson.checks.first() if session.lesson_id else None
    if check is None:
        return None
    return {
        "id": str(check.pk), "question": check.question, "answer": check.answer,
        "distractors": check.distractors, "threshold": check.threshold,
    }


def _note(note):
    return {
        "id": str(note.pk),
        "pupil": str(note.pupil_id) if note.pupil_id else None,
        "group": str(note.group_id) if note.group_id else None,
        "type": str(note.note_type_id) if note.note_type_id else None,
        "text": note.text,
        "actionable": note.actionable,
        "done": note.done_at is not None,
        "at": note.created_at.isoformat(),
    }


def _plan(session):
    """
    The lesson's plan as the panel and strip use it, with the period's start so the page can tell
    the time, and what was carried in from earlier lessons. None when there is neither.
    """
    from plans.sweep import carried_into
    from timetable.models import Timetable

    carried = [
        {"text": c.plan_activity.text, "from": f"{c.session.date:%a} {c.session.date.day} {c.session.date:%b}"}
        for c in carried_into(session)
    ]
    lesson = session.lesson
    if lesson is None and not carried:
        return None
    start, end = Timetable.active().period_times(session.period)

    def at(time):
        return timezone.make_aware(datetime.datetime.combine(session.date, time)).isoformat() if time else None

    return {
        "title": str(lesson) if lesson else "Carried forward",
        "objective": lesson.objective if lesson else "",
        "activities": [{"id": str(a.pk), "text": a.text, "minutes": a.minutes} for a in lesson.activities.all()] if lesson else [],
        "homework": lesson.homework if lesson else "",
        "start": at(start),
        "end": at(end),
        "carried": carried,
    }
