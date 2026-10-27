"""Catch tempo: Today and the room view. Nothing here asks for input."""

from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from rooms.models import SEAT_HEIGHT, SEAT_WIDTH, SeatingPlan

from .models import Session, Timetable
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
    plan = SeatingPlan.current(session.klass, room, session.date)

    seated = {}
    elsewhere = None
    if plan:
        seated = {a.seat_id: a.pupil for a in plan.assignments.select_related("pupil")}
    else:
        elsewhere = SeatingPlan.objects.filter(klass=session.klass).exclude(room=room).select_related("room").first()

    return render(request, "timetable/room_view.html", {
        "session": session,
        "room": room,
        "plan": plan,
        "elsewhere": elsewhere,
        "seats": [{"seat": seat, "pupil": seated.get(seat.id)} for seat in room.seats.all()],
        "next": next_session(session, timetable),
        "seat_width": SEAT_WIDTH,
        "seat_height": SEAT_HEIGHT,
    })
