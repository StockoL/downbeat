from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import UserCreationForm
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
    """
    First run: the teacher's account (only if none exists), the timetable, note types and a
    first room, saved together or not at all.
    """
    data = request.POST if request.method == "POST" else None
    has_account = get_user_model().objects.exists()
    if Timetable.objects.exists():
        if has_account:
            return redirect("today")
        return account_only(request, data)

    account_form = None if has_account else UserCreationForm(data, prefix="account")
    timetable_form = TimetableForm(data, prefix="timetable")
    periods = PeriodFormSet(data, prefix="periods")
    note_types = NoteTypeFormSet(data, prefix="notetypes", queryset=NoteType.objects.none())
    room_form = RoomForm(data, prefix="room")
    forms = [f for f in [account_form, timetable_form, periods, note_types, room_form] if f is not None]

    if data is not None and all(f.is_valid() for f in forms):
        with transaction.atomic():
            user = account_form.save() if account_form is not None else None
            timetable = timetable_form.save(commit=False)
            timetable.periods = periods.as_periods()
            timetable.save()
            for order, note_type in enumerate(note_types.save(commit=False)):
                note_type.order = order
                note_type.save()
            room_form.save()
        if user is not None:
            login(request, user)
        return redirect("today")

    return render(request, "core/setup.html", {
        "account_form": account_form,
        "timetable_form": timetable_form,
        "periods": periods,
        "note_types": note_types,
        "room_form": room_form,
    })


def account_only(request, data):
    """An install from before sign-in existed: it has a timetable but no account. Create just the account."""
    account_form = UserCreationForm(data, prefix="account")
    if data is not None and account_form.is_valid():
        login(request, account_form.save())
        return redirect("today")
    return render(request, "core/setup.html", {"account_form": account_form, "account_only": True})


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
