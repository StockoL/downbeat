from django.db import transaction
from django.shortcuts import redirect, render

from notes.models import NoteType
from timetable.models import Timetable

from .forms import NoteTypeFormSet, PeriodFormSet, RoomForm, TimetableForm


def settings_home(request):
    return render(request, "core/settings.html", {"nav": "settings"})


def setup(request):
    """First run: the timetable, note types and a first room, saved together or not at all."""
    if Timetable.objects.exists():
        return redirect("today")

    data = request.POST if request.method == "POST" else None
    timetable_form = TimetableForm(data, prefix="timetable")
    periods = PeriodFormSet(data, prefix="periods")
    note_types = NoteTypeFormSet(data, prefix="notetypes", queryset=NoteType.objects.none())
    room_form = RoomForm(data, prefix="room")
    forms = [timetable_form, periods, note_types, room_form]

    if data is not None and all(f.is_valid() for f in forms):
        with transaction.atomic():
            timetable = timetable_form.save(commit=False)
            timetable.periods = periods.as_periods()
            timetable.save()
            for order, note_type in enumerate(note_types.save(commit=False)):
                note_type.order = order
                note_type.save()
            room_form.save()
        return redirect("today")

    return render(request, "core/setup.html", {
        "timetable_form": timetable_form,
        "periods": periods,
        "note_types": note_types,
        "room_form": room_form,
    })
