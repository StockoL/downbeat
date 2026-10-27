"""Catch tempo: the note sheet, inbox and actions, all sheets over the room view."""

from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from timetable.models import Pupil, Session

from . import services
from .models import Note, NoteType


def room_update(request, session, pupils=(), *, close_sheet=False, sheet=None, sheet_main=None, **sheet_context):
    """
    Out-of-band fragments that keep the room view in step after a change: the log,
    the touched pupils' seat marks and the actions counter. Optionally a template for the sheet.
    """
    context = {
        "session": session,
        "log": services.log(session),
        "undo_count": services.undo_count(request, session),
        "states": services.seat_states(session, pupils),
        "actions_count": len(services.actions(session)),
        "sheet": sheet,
        "sheet_main": sheet_main,
        **sheet_context,
    }
    response = render(request, "notes/_room_update.html", context)
    if close_sheet:
        response["HX-Trigger"] = "closeSheet"
    return response


def note_sheet(request, session_pk, pupil_pk):
    session = get_object_or_404(Session, pk=session_pk)
    pupil = get_object_or_404(Pupil, pk=pupil_pk)
    state = services.seat_states(session, [pupil])[0]
    return render(request, "notes/sheet.html", {
        "session": session,
        "pupil": pupil,
        "state": state,
        "note_types": services.sheet_types(),
        "free_text": request.GET.get("free") is not None,
    })


@require_POST
def note_add(request, session_pk):
    """One tap on a note type records the note. Free text is the only path that sends text."""
    session = get_object_or_404(Session, pk=session_pk)
    pupil = get_object_or_404(Pupil, pk=request.POST.get("pupil"))
    type_id = request.POST.get("note_type")
    if type_id:
        note = services.add(session, pupil, get_object_or_404(NoteType, pk=type_id))
    else:
        text = request.POST.get("text", "").strip()
        if not text:
            return room_update(request, session, [pupil], close_sheet=True)
        note = services.add(session, pupil, text=text, actionable=request.POST.get("actionable") == "on")
    services.push_undo(request, session, "add", note)
    return room_update(request, session, [pupil], close_sheet=True)


@require_POST
def note_remove(request, pk):
    note = get_object_or_404(Note.objects.select_related("session", "pupil"), pk=pk)
    services.remove(note)
    services.push_undo(request, note.session, "remove", note)
    return room_update(request, note.session, [note.pupil] if note.pupil else [])


@require_POST
def note_undo(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    note = services.undo(request, session)
    return room_update(request, session, [note.pupil] if note and note.pupil else [])


def inbox(request, session_pk, pupil_pk):
    """A pupil's notes, newest first. Reached only from the unread counter."""
    session = get_object_or_404(Session, pk=session_pk)
    pupil = get_object_or_404(Pupil, pk=pupil_pk)
    notes = pupil.notes.live().select_related("note_type", "session__klass").order_by("-created_at")[:50]
    return render(request, "notes/inbox.html", {"session": session, "pupil": pupil, "notes": notes})


def actions_sheet(request, session_pk):
    session = get_object_or_404(Session.objects.select_related("klass"), pk=session_pk)
    return render(request, "notes/actions.html", {"session": session, "actions": services.actions(session)})


@require_POST
def action_done(request, pk):
    note = get_object_or_404(Note.objects.select_related("pupil"), pk=pk)
    session = get_object_or_404(Session, pk=request.POST.get("session"))
    note.done_at = timezone.now()
    note.save(update_fields=["done_at", "updated_at"])
    return room_update(
        request, session, [note.pupil] if note.pupil else [],
        sheet="notes/actions.html", actions=services.actions(session),
    )


@require_POST
def spoken_toggle(request, session_pk):
    """The one-tap toggle at the top of the note sheet. Closes the sheet."""
    session = get_object_or_404(Session, pk=session_pk)
    pupil = get_object_or_404(Pupil, pk=request.POST.get("pupil"))
    services.toggle_spoken(session, pupil)
    return room_update(request, session, [pupil], close_sheet=True)


@require_POST
def absent_toggle(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    pupil = get_object_or_404(Pupil, pk=request.POST.get("pupil"))
    services.toggle_absent(session, pupil)
    return room_update(request, session, [pupil], close_sheet=True)


@require_POST
def pick(request, session_pk):
    """
    Draw a name and record spoken-to. "absent" first marks the last drawn pupil absent and
    takes back their draw, so a name called to an empty chair costs one tap.
    """
    session = get_object_or_404(Session, pk=session_pk)
    whole_class = request.POST.get("whole_class") == "1"
    touched = []
    if request.POST.get("absent"):
        away = get_object_or_404(Pupil, pk=request.POST["absent"])
        services.undraw(session, away)
        if away.pk not in services.absent(session):
            services.toggle_absent(session, away)
        touched.append(away)
    pupil = services.draw(session, whole_class=whole_class)
    if pupil:
        touched.append(pupil)
    return room_update(
        request, session, touched, sheet_main="notes/picker.html", picked=pupil, whole_class=whole_class,
    )
