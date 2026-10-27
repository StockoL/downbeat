"""
Prep (inside Sweep): tomorrow's sessions with what to print, set up and chase, generated from the
plans and the open actions, plus the teacher's own items. Ticks are kept.
"""

import datetime

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from notes import services as notes
from timetable.models import Session, Timetable
from timetable.services import sessions_on

from .models import PrepItem


def next_teaching_day(after):
    """The next date after `after` that has any session that isn't cancelled (looking up to three weeks on)."""
    upcoming = (
        Session.objects.filter(date__gt=after, date__lte=after + datetime.timedelta(weeks=3))
        .exclude(status=Session.CANCELLED).order_by("date").values_list("date", flat=True).first()
    )
    return upcoming or after + datetime.timedelta(days=1)


def generated(session):
    """(source, text) pairs Prep should list for a session, from its lesson's resources and the class's open actions."""
    items = []
    if session.lesson_id:
        for resource in session.lesson.resources.all():
            where = f" ({resource.path_or_url})" if resource.path_or_url else ""
            if resource.needs_print:
                items.append((PrepItem.RESOURCE, f"Print {resource.copies or ''}{' × ' if resource.copies else ''}{resource.title}{where}"))
            if resource.setup_note:
                items.append((PrepItem.RESOURCE, f"Set up: {resource.title}: {resource.setup_note}"))
    for note in notes.actions(session):
        who = note.pupil or note.group or "Class"
        detail = note.note_type.label if note.note_type else note.text
        items.append((PrepItem.ACTION, f"Chase: {who} · {detail}"))
    return items


@transaction.atomic
def refresh(session):
    """Bring a session's generated items up to date. Ticked items are never removed."""
    wanted = set(generated(session))
    existing = {(i.source, i.text): i for i in session.prep_items.exclude(source=PrepItem.MANUAL)}
    for key, item in existing.items():
        if key not in wanted and item.done_at is None:
            item.delete()
    PrepItem.objects.bulk_create([
        PrepItem(session=session, source=source, text=text[:300]) for source, text in wanted if (source, text) not in existing
    ])


def prep(request):
    today = timezone.localdate()
    try:
        day = datetime.date.fromisoformat(request.GET["date"])
    except (KeyError, ValueError):
        day = next_teaching_day(today)
    sessions = [s for s in sessions_on(day, Timetable.active()) if s.status != Session.CANCELLED]
    for session in sessions:
        refresh(session)
        session.items = list(session.prep_items.all())
    return render(request, "sweep/prep.html", {
        "nav": "sweep", "day": day, "sessions": sessions,
        "previous": day - datetime.timedelta(days=1), "following": day + datetime.timedelta(days=1),
    })


def _back(session):
    return f"{reverse('prep')}?date={session.date.isoformat()}"


@require_POST
def prep_toggle(request, pk):
    item = get_object_or_404(PrepItem.objects.select_related("session"), pk=pk)
    item.done_at = None if item.done_at else timezone.now()
    item.save(update_fields=["done_at", "updated_at"])
    return redirect(_back(item.session))


@require_POST
def prep_add(request, pk):
    session = get_object_or_404(Session, pk=pk)
    text = request.POST.get("text", "").strip()[:300]
    if text:
        PrepItem.objects.get_or_create(session=session, source=PrepItem.MANUAL, text=text)
    else:
        messages.error(request, "Type the item first.")
    return redirect(_back(session))


@require_POST
def prep_remove(request, pk):
    item = get_object_or_404(PrepItem.objects.select_related("session"), pk=pk, source=PrepItem.MANUAL)
    item.delete()
    return redirect(_back(item.session))
