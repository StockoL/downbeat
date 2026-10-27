"""What the room view shows of notes, and the changes made from it."""

from django.utils import timezone

from timetable.models import Timetable
from timetable.services import period_order, previous_session

from .models import Note, NoteType


def sheet_types():
    """The note sheet's buttons: house point first, then the teacher's order."""
    return NoteType.objects.order_by("-is_house_point", "order", "label")


def log(session):
    return session.notes.live().select_related("pupil", "note_type")



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




