"""Plan area: per-class seating plans. Desk work, so drag freely and undo freely."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from pupils.services import flag_colours
from timetable.models import Class, Pupil

from . import seating
from .models import SEAT_HEIGHT, SEAT_WIDTH, Room, Seat, SeatingPlan


def plan_home(request):
    classes = Class.objects.prefetch_related("seating_plans__room")
    return render(request, "rooms/plan_home.html", {"nav": "plan", "classes": classes, "rooms": Room.objects.all()})


def board_context(request, plan, message=""):
    assignments = {a.seat_id: a for a in plan.assignments.select_related("pupil")}
    seated = {a.pupil_id for a in assignments.values()}
    flags = flag_colours(plan.klass.pupils.values_list("id", flat=True))
    seats = [
        {"seat": seat, "assignment": a, "flags": flags.get(a.pupil_id) if a else None}
        for seat in plan.room.seats.all()
        for a in [assignments.get(seat.id)]
    ]
    return {
        "plan": plan,
        "room": plan.room,
        "seats": seats,
        "unseated": [p for p in plan.klass.pupils.all() if p.id not in seated],
        "undo_count": seating.undo_count(request.session, plan),
        "seat_width": SEAT_WIDTH,
        "seat_height": SEAT_HEIGHT,
        "message": message,
    }


def seating_edit(request, pk):
    plan = get_object_or_404(SeatingPlan.objects.select_related("klass", "room"), pk=pk)
    return render(request, "rooms/seating_edit.html", {"nav": "plan", **board_context(request, plan)})


def _board(request, plan, message="", status=200):
    return render(request, "rooms/_plan_board.html", board_context(request, plan, message), status=status)


@require_POST
def seating_create(request):
    klass = get_object_or_404(Class, pk=request.POST.get("klass"))
    room = get_object_or_404(Room, pk=request.POST.get("room"))
    plan, source = seating.create_plan(klass, room, timezone.localdate())
    if source:
        messages.success(request, f"Seated {plan.assignments.count()} of {klass.pupils.count()} by zone from {source.room}.")
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("seating_edit", pk=plan.pk)


@require_POST
def seating_move(request, pk):
    """Drop a pupil on a seat, or on the bin (seat="bin") to unseat them."""
    plan = get_object_or_404(SeatingPlan, pk=pk)
    pupil = get_object_or_404(Pupil, pk=request.POST.get("pupil"))
    try:
        if request.POST.get("seat") == "bin":
            snap = seating.unseat(plan, pupil)
        else:
            snap = seating.move(plan, pupil, get_object_or_404(Seat, pk=request.POST.get("seat"), room=plan.room))
    except seating.SeatLocked:
        return _board(request, plan, "That seat is locked. Tap it to unlock.", status=409)
    seating.push_undo(request.session, plan, snap)
    return _board(request, plan)


@require_POST
def seating_lock(request, pk):
    plan = get_object_or_404(SeatingPlan, pk=pk)
    seat = get_object_or_404(Seat, pk=request.POST.get("seat"), room=plan.room)
    seating.push_undo(request.session, plan, seating.toggle_lock(plan, seat))
    return _board(request, plan)


@require_POST
def seating_undo(request, pk):
    plan = get_object_or_404(SeatingPlan, pk=pk)
    snap = seating.pop_undo(request.session, plan)
    if snap:
        seating.restore(plan, snap)
    return _board(request, plan)


@require_POST
def seating_delete(request, pk):
    plan = get_object_or_404(SeatingPlan, pk=pk)
    plan.delete()
    messages.success(request, f"Deleted the seating plan for {plan.klass} in {plan.room}.")
    return redirect("plan_home")
