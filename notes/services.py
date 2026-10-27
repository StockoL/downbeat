"""What the room view shows of notes, and the changes made from it."""

from collections import defaultdict

from django.db.models import Count
from django.utils import timezone

from timetable.models import Timetable
from timetable.services import period_order

from .models import Note, NoteType

UNDO_LIMIT = 10


def sheet_types():
    """The note sheet's buttons: house point first, then the teacher's order."""
    return NoteType.objects.order_by("-is_house_point", "order", "label")


def log(session):
    return session.notes.live().select_related("pupil", "note_type")


def badges(session, pupil_ids=None):
    """{pupil_id: [icon, ...]} for notes made this session, in the order they were made."""
    notes = session.notes.live().filter(pupil__isnull=False).select_related("note_type")
    if pupil_ids is not None:
        notes = notes.filter(pupil_id__in=pupil_ids)
    icons = defaultdict(list)
    for note in notes:
        icons[note.pupil_id].append(note.icon)
    return icons


def unread(pupil_ids):
    """{pupil_id: count} of each pupil's open actions, from any session: the inbox counter."""
    rows = Note.objects.open_actions().filter(pupil_id__in=pupil_ids).values("pupil_id").annotate(n=Count("id"))
    return {row["pupil_id"]: row["n"] for row in rows}


def actions(session):
    """
    Open actions for this session's class: from this session and every earlier one with the class.
    Those from earlier sessions are recorded as carried to this one.
    """
    order = period_order(Timetable.active())
    rank = lambda s: (s.date, order.get(s.period, len(order)))
    notes = Note.objects.open_actions().filter(
        session__klass=session.klass, session__date__lte=session.date,
    ).select_related("pupil", "note_type", "session").order_by("session__date", "created_at")
    notes = [n for n in notes if n.session_id == session.id or rank(n.session) < rank(session)]
    carried = [n.pk for n in notes if n.session_id != session.id and n.carried_to_session_id != session.id]
    if carried:
        Note.objects.filter(pk__in=carried).update(carried_to_session=session, updated_at=timezone.now())
    return notes


def add(session, pupil, note_type=None, text="", actionable=None):
    if actionable is None:
        actionable = bool(note_type and note_type.is_actionable_default)
    return Note.objects.create(session=session, pupil=pupil, note_type=note_type, text=text.strip(), actionable=actionable)


def remove(note):
    note.deleted_at = timezone.now()
    note.save(update_fields=["deleted_at", "updated_at"])


def restore(note):
    note.deleted_at = None
    note.save(update_fields=["deleted_at", "updated_at"])


def push_undo(request, session, action, note):
    key = f"note-undo:{session.pk}"
    stack = request.session.get(key, [])
    stack.append([action, str(note.pk)])
    request.session[key] = stack[-UNDO_LIMIT:]


def undo(request, session):
    """Reverse the last add or remove in this session. Returns the note touched, or None."""
    key = f"note-undo:{session.pk}"
    stack = request.session.get(key, [])
    if not stack:
        return None
    action, note_id = stack.pop()
    request.session[key] = stack
    note = Note.objects.filter(pk=note_id, session=session).first()
    if note is None:
        return None
    if action == "add":
        remove(note)
    else:
        restore(note)
    return note


def undo_count(request, session):
    return len(request.session.get(f"note-undo:{session.pk}", []))
