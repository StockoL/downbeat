"""What the room view shows of notes, and the changes made from it."""

import random
from collections import defaultdict

from django.db.models import Count
from django.utils import timezone

from timetable.models import SessionAttendance, Timetable
from timetable.services import period_order, previous_session

from .models import Note, NoteType, SpokenTo

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
    def rank(s):
        return (s.date, order.get(s.period, len(order)))
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


# --- Spoken to, absence and the picker ---------------------------------------

def spoken(session):
    return set(session.spoken_to.values_list("pupil_id", flat=True))


def absent(session):
    return set(session.attendance.filter(present=False).values_list("pupil_id", flat=True))


def missed_last_time(session):
    """
    Pupils of this class with no spoken-to row in the previous session with the class.
    Empty if spoken-to wasn't used at all last time, so an unused feature never highlights everyone.
    """
    previous = previous_session(session, Timetable.active())
    if previous is None:
        return set()
    had_turn = spoken(previous)
    if not had_turn:
        return set()
    return set(session.klass.pupils.values_list("id", flat=True)) - had_turn


def seat_states(session, pupils):
    """Everything a seat shows about each pupil, keyed in the order given."""
    ids = [p.pk for p in pupils]
    icons = badges(session, ids)
    counts = unread(ids)
    spoke, away, missed = spoken(session), absent(session), missed_last_time(session)
    return [
        {
            "pupil": p, "badges": icons.get(p.pk, []), "unread": counts.get(p.pk, 0),
            "spoken": p.pk in spoke, "absent": p.pk in away, "missed": p.pk in missed,
        }
        for p in pupils
    ]


def toggle_spoken(session, pupil):
    """Tap once to record, again to take it back. Returns whether they are now spoken to."""
    rows = SpokenTo.objects.filter(session=session, pupil=pupil)
    if rows.exists():
        rows.delete()
        return False
    SpokenTo.objects.create(session=session, pupil=pupil)
    return True


def toggle_absent(session, pupil):
    """Returns whether the pupil is now marked absent."""
    row, _ = SessionAttendance.objects.get_or_create(session=session, pupil=pupil)
    row.present = not row.present
    row.save(update_fields=["present", "updated_at"])
    return not row.present


def draw(session, whole_class=False, rng=random):
    """
    Pick a present pupil and record a spoken-to row. By default only those not yet spoken to
    this lesson; once everyone has had a turn, the whole class again. Returns the pupil or None.
    """
    away, spoke = absent(session), spoken(session)
    present = [p for p in session.klass.pupils.all() if p.pk not in away]
    pool = present if whole_class else [p for p in present if p.pk not in spoke] or present
    if not pool:
        return None
    pupil = rng.choice(pool)
    SpokenTo.objects.create(session=session, pupil=pupil)
    return pupil


def undraw(session, pupil):
    """Take back the latest spoken-to row for a pupil, for a draw that landed on someone absent."""
    row = SpokenTo.objects.filter(session=session, pupil=pupil).order_by("-created_at").first()
    if row:
        row.delete()
