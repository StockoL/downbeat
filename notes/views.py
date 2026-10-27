"""
Catch tempo, server side. The room view captures everything through the device's queue, which
arrives at `sync_ops`; `state` is what the page draws from. The inbox is the one read that stays
online-only: past notes are not for reading mid-lesson.
"""

import json

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from timetable.models import Pupil, Session

from . import sync
from .state import lesson_state

MAX_OPS = 500


@require_GET
def state(request, session_pk):
    session = get_object_or_404(Session.objects.select_related("klass", "room"), pk=session_pk)
    return JsonResponse(lesson_state(session))


@require_POST
def sync_ops(request):
    """Apply a device's queued operations. Answers with the ids it can drop from its queue."""
    try:
        ops = json.loads(request.body).get("ops", [])
    except (ValueError, AttributeError):
        return HttpResponseBadRequest('Expected JSON: {"ops": [...]}')
    if not isinstance(ops, list) or len(ops) > MAX_OPS or not all(isinstance(op, dict) for op in ops):
        return HttpResponseBadRequest(f"Expected up to {MAX_OPS} operations")
    applied, rejected = sync.apply(ops)
    return JsonResponse({"applied": applied, "rejected": rejected})


@require_GET
def inbox(request, session_pk, pupil_pk):
    """A pupil's notes, newest first. Reached only from the unread counter."""
    session = get_object_or_404(Session, pk=session_pk)
    pupil = get_object_or_404(Pupil, pk=pupil_pk)
    notes = pupil.notes.live().select_related("note_type", "session__klass").order_by("-created_at")[:50]
    return render(request, "notes/inbox.html", {"session": session, "pupil": pupil, "notes": notes})
