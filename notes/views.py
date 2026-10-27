"""Catch tempo: the note sheet, inbox and actions, all sheets over the room view."""

from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from timetable.models import Pupil, Session

from . import services
from .models import Note, NoteType


def room_update(request, session, pupils=(), *, close_sheet=False, sheet=None):
    """
    Out-of-band fragments that keep the room view in step after a change: the log,
    the touched pupils' seat marks and the actions counter. Optionally the sheet's content.
    """
    pupil_ids = [p.pk for p in pupils]
    badges = services.badges(session, pupil_ids)
    unread = services.unread(pupil_ids)
    context = {
        "session": session,
        "log": services.log(session),
        "undo_count": services.undo_count(request, session),
        "marks": [{"pupil": p, "badges": badges.get(p.pk, []), "unread": unread.get(p.pk, 0)} for p in pupils],
        "actions_count": len(services.actions(session)),
        "sheet": sheet,
    }
    response = render(request, "notes/_room_update.html", context)
    if close_sheet:
        response["HX-Trigger"] = "closeSheet"
    return response


def note_sheet(request, session_pk, pupil_pk):
    session = get_object_or_404(Session, pk=session_pk)
    pupil = get_object_or_404(Pupil, pk=pupil_pk)
    return render(request, "notes/sheet.html", {
        "session": session,
        "pupil": pupil,
        "badges": services.badges(session, [pupil.pk]).get(pupil.pk, []),
        "unread": services.unread([pupil.pk]).get(pupil.pk, 0),
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
        sheet={"template": "notes/actions.html", "actions": services.actions(session)},
    )
