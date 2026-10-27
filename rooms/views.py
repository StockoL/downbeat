from django.contrib import messages
from django.db.models import Count, ProtectedError
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import AddSeatsForm, RoomForm
from .models import SEAT_HEIGHT, SEAT_WIDTH, Room, Seat


def _render(request, template, context):
    return render(request, template, {"nav": "settings", "section": "rooms", **context})


def _clamp(value, high):
    return max(0, min(int(value), high))


def room_list(request):
    form = RoomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        room = form.save()
        return redirect("room_edit", pk=room.pk)
    rooms = Room.objects.annotate(seat_count=Count("seats"))
    return _render(request, "rooms/room_list.html", {"form": form, "rooms": rooms})


def room_edit(request, pk):
    room = get_object_or_404(Room, pk=pk)
    form = RoomForm(request.POST or None, instance=room)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Room saved.")
        return redirect("room_edit", pk=room.pk)
    return _render(request, "rooms/room_edit.html", {
        "room": room, "form": form, "add_form": AddSeatsForm(), "seats": room.seats.all(),
        "zones": Seat.ZONES, "seat_width": SEAT_WIDTH, "seat_height": SEAT_HEIGHT,
        # An unplaced marker starts at the front centre, where it is easy to find and drag.
        "teacher_x": room.canvas_width // 2 if room.teacher_x is None else room.teacher_x,
        "teacher_y": room.canvas_height - 40 if room.teacher_y is None else room.teacher_y,
    })


@require_POST
def room_delete(request, pk):
    room = get_object_or_404(Room, pk=pk)
    try:
        room.delete()
        messages.success(request, f"Deleted {room}.")
        return redirect("room_list")
    except ProtectedError:
        messages.error(request, "This room is used by slots or sessions. Move them to another room first.")
        return redirect("room_edit", pk=room.pk)


@require_POST
def seats_add(request, pk):
    """New seats go in a row below the lowest existing seat, wrapping at the canvas edge."""
    room = get_object_or_404(Room, pk=pk)
    form = AddSeatsForm(request.POST)
    if not form.is_valid():
        return redirect("room_edit", pk=room.pk)
    lowest = max((s.y for s in room.seats.all()), default=-SEAT_HEIGHT - 20)
    gap = 20
    x, y = gap, min(lowest + SEAT_HEIGHT + gap, room.canvas_height - SEAT_HEIGHT)
    number = room.seats.count()
    for _ in range(form.cleaned_data["count"]):
        number += 1
        Seat.objects.create(room=room, x=x, y=y, label=str(number))
        x += SEAT_WIDTH + gap
        if x > room.canvas_width - SEAT_WIDTH:
            x, y = gap, min(y + SEAT_HEIGHT + gap, room.canvas_height - SEAT_HEIGHT)
    return redirect("room_edit", pk=room.pk)


@require_POST
def seat_update(request, pk):
    """Partial update from the canvas: any of x, y, label, zone, near_teacher."""
    seat = get_object_or_404(Seat.objects.select_related("room"), pk=pk)
    data = request.POST
    try:
        if "x" in data:
            seat.x = _clamp(float(data["x"]), seat.room.canvas_width - SEAT_WIDTH)
        if "y" in data:
            seat.y = _clamp(float(data["y"]), seat.room.canvas_height - SEAT_HEIGHT)
    except ValueError:
        return HttpResponseBadRequest("x and y must be numbers")
    if "label" in data:
        seat.label = data["label"].strip()[:20]
    if "zone" in data:
        if data["zone"] not in dict(Seat.ZONES) and data["zone"] != "":
            return HttpResponseBadRequest("Unknown zone")
        seat.zone = data["zone"]
    if "near_teacher" in data:
        seat.near_teacher = data["near_teacher"] in ("1", "true", "on")
    seat.save()
    return JsonResponse(seat.as_dict())


@require_POST
def seat_delete(request, pk):
    seat = get_object_or_404(Seat, pk=pk)
    seat.delete()
    return JsonResponse({"deleted": str(pk)})


@require_POST
def teacher_move(request, pk):
    room = get_object_or_404(Room, pk=pk)
    try:
        room.teacher_x = _clamp(float(request.POST["x"]), room.canvas_width)
        room.teacher_y = _clamp(float(request.POST["y"]), room.canvas_height)
    except (KeyError, ValueError):
        return HttpResponseBadRequest("x and y are required")
    room.save(update_fields=["teacher_x", "teacher_y", "updated_at"])
    return JsonResponse({"x": room.teacher_x, "y": room.teacher_y})
