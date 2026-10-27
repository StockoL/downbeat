"""Catch tempo: Today and the room view. Nothing here asks for input."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from notes.services import sheet_types
from notes.state import lesson_state
from pupils.services import active_groups, flag_colours, group_tints
from rooms.cover import cover_pdf
from rooms.models import SEAT_HEIGHT, SEAT_WIDTH, SeatingPlan
from rooms.seating import seating_for

from .models import Session, Timetable
from .rotations import out_of
from .services import live_session, next_session, sessions_on


def today(request):
    """Lands on the live session's room view; the list shows otherwise, or with ?list."""
    timetable = Timetable.active()
    now = timezone.localtime()
    if "list" not in request.GET:
        live = live_session(now, timetable)
        if live:
            return redirect("room_view", pk=live.pk)

    sessions = sessions_on(now.date(), timetable)
    for session in sessions:
        session.out = len(out_of(session))
    current = next((s for s in sessions if s.status != Session.CANCELLED and s.end and now.time() < s.end), None)
    upcoming = None
    if not sessions:
        upcoming = Session.objects.filter(date__gt=now.date()).exclude(status=Session.CANCELLED).order_by("date").first()
    return render(request, "timetable/today.html", {
        "nav": "today", "sessions": sessions, "current": current, "upcoming": upcoming, "now": now,
    })


def room_view(request, pk):
    session = get_object_or_404(Session.objects.select_related("klass", "room"), pk=pk)
    timetable = Timetable.active()
    session.start, session.end = timetable.period_times(session.period)
    room = session.room
    plan, seated, unseated = seating_for(session)
    elsewhere = None
    if plan is None:
        elsewhere = SeatingPlan.objects.filter(klass=session.klass).exclude(room=room).select_related("room").first()
    flags = flag_colours([p.pk for p in [*seated.values(), *unseated]])
    tints = group_tints(session.klass)

    def marks(pupil):
        return {"flags": flags.get(pupil.pk), "tint": tints.get(pupil.pk)} if pupil else {}

    return render(request, "timetable/room_view.html", {
        "session": session,
        "room": room,
        "plan": plan,
        "elsewhere": elsewhere,
        "seats": [{"seat": seat, "pupil": seated.get(seat.id), **marks(seated.get(seat.id))} for seat in room.seats.all()],
        "unseated": [{"pupil": p, **marks(p)} for p in unseated],
        "groups": active_groups(session.klass),
        "state": lesson_state(session),
        "note_types": sheet_types(),
        "next": next_session(session, timetable),
        "seat_width": SEAT_WIDTH,
        "seat_height": SEAT_HEIGHT,
    })


def projector(request, pk):
    """Names on the room layout, high contrast, nothing else. The only view meant for a screen pupils see."""
    session = get_object_or_404(Session.objects.select_related("klass", "room"), pk=pk)
    _, seated, _ = seating_for(session)
    return render(request, "timetable/projector.html", {
        "session": session,
        "room": session.room,
        "seats": [{"seat": seat, "pupil": seated.get(seat.id)} for seat in session.room.seats.all()],
        "seat_width": SEAT_WIDTH,
        "seat_height": SEAT_HEIGHT,
    })


def cover(request, pk):
    session = get_object_or_404(Session.objects.select_related("klass", "room"), pk=pk)
    _, seated, unseated = seating_for(session)
    response = HttpResponse(cover_pdf(session, seated, unseated), content_type="application/pdf")
    filename = slugify(f"cover {session.klass} {session.room} {session.date:%Y-%m-%d}")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response
