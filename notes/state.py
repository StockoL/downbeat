"""
A lesson's state as plain data: what the room view draws its sheets, log, seat marks, actions
and picker from. The page holds it, applies the device's unsent operations on top, and fetches
it again after each successful sync, so the laptop stays the source of truth.
"""

from collections import Counter

from rooms.seating import seating_for

from . import services
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
        "notes": [_note(n) for n in services.log(session)],
        "actions": [{**_note(n), "when": when(n)} for n in actions],
        # Open actions for each pupil from other classes, so the unread counter covers them too.
        "elsewhere": {str(pk): totals[pk] - in_class[pk] for pk in pupil_ids if totals[pk] > in_class[pk]},
        "spoken": spoken,
        "absent": [str(pk) for pk in services.absent(session)],
        "missed": [str(pk) for pk in services.missed_last_time(session)],
    }


def _note(note):
    return {
        "id": str(note.pk),
        "pupil": str(note.pupil_id) if note.pupil_id else None,
        "type": str(note.note_type_id) if note.note_type_id else None,
        "text": note.text,
        "actionable": note.actionable,
        "done": note.done_at is not None,
        "at": note.created_at.isoformat(),
    }
