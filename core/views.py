from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from notes.models import NoteType
from timetable.models import Timetable

from . import data
from .forms import NoteTypeFormSet, PeriodFormSet, RoomForm, TimetableForm

DELETE_PHRASE = "delete everything"


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


# --- Settings → Data ----------------------------------------------------------

def data_page(request):
    return render(request, "core/data.html", {
        "nav": "settings", "section": "data",
        "backup_dir": settings.BACKUP_DIR, "backups": data.list_backups()[:10], "delete_phrase": DELETE_PHRASE,
    })


@require_POST
def data_backup(request):
    try:
        path = data.backup()
        messages.success(request, f"Backed up to {path.name}.")
    except data.BackupFailed as error:
        messages.error(request, str(error))
    return redirect("data_page")


def data_export(request):
    response = HttpResponse(data.export_json(), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="downbeat-export-{timezone.localdate():%Y-%m-%d}.json"'
    return response


@require_POST
def data_delete_all(request):
    """Only with the phrase typed out. Backups are separate files and are left alone."""
    if request.POST.get("confirm", "").strip().lower() != DELETE_PHRASE:
        messages.error(request, f'Nothing was deleted. Type "{DELETE_PHRASE}" to confirm.')
        return redirect("data_page")
    data.delete_all()
    return redirect("setup")
