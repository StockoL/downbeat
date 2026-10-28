import datetime

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import PeriodFormSet

from .forms import (
    AddPupilsForm,
    ClassForm,
    GenerateSessionsForm,
    PupilForm,
    SessionForm,
    SlotForm,
    TimetableEditForm,
    parse_pupil_lines,
)
from .models import Class, Pupil, Session, Slot, Timetable
from .services import generate_sessions


def _render(request, template, context, section):
    return render(request, template, {"nav": "settings", "section": section, **context})


def _delete(request, obj, redirect_to, blocked_message):
    try:
        obj.delete()
        messages.success(request, f"Deleted {obj}.")
    except ProtectedError:
        messages.error(request, blocked_message)
    return redirect(redirect_to)


# --- Timetable ---------------------------------------------------------------

def timetable_edit(request):
    timetable = Timetable.active()
    data = request.POST if request.method == "POST" else None
    form = TimetableEditForm(data, instance=timetable, prefix="timetable")
    initial = [{"label": p["label"], "start": p["start"], "end": p["end"]} for p in timetable.periods]
    periods = PeriodFormSet(data, prefix="periods", initial=initial)
    if data is not None and form.is_valid() and periods.is_valid():
        timetable = form.save(commit=False)
        timetable.periods = periods.as_periods()
        timetable.save()
        messages.success(request, "Timetable saved.")
        return redirect("timetable_edit")
    return _render(request, "timetable/timetable_form.html", {"form": form, "periods": periods}, "timetable")


# --- Slots -------------------------------------------------------------------

def slot_list(request):
    timetable = Timetable.active()
    form = SlotForm(request.POST or None, timetable=timetable)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Added {form.instance}.")
        return redirect("slot_list")

    slots = list(Slot.objects.filter(timetable=timetable).select_related("klass", "room"))
    weeks = ["A", "B"] if timetable.week_cycle == 2 else ["A"]
    grids = []
    for week in weeks:
        rows = []
        for period in timetable.periods:
            cells = [
                [s for s in slots if s.week == week and s.day == day and s.period == period["label"]]
                for day, _ in Slot.DAYS
            ]
            rows.append({"period": period, "cells": cells})
        grids.append({"week": week, "rows": rows})
    orphans = [s for s in slots if timetable.period(s.period) is None]
    return _render(request, "timetable/slot_list.html", {
        "form": form, "grids": grids, "days": Slot.DAYS, "two_week": timetable.week_cycle == 2, "orphans": orphans,
    }, "slots")


def slot_edit(request, pk):
    slot = get_object_or_404(Slot, pk=pk)
    form = SlotForm(request.POST or None, instance=slot, timetable=slot.timetable)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved {slot}.")
        return redirect("slot_list")
    return _render(request, "timetable/object_form.html", {
        "form": form, "title": f"Edit {slot}", "back": "slot_list", "delete_url": "slot_delete", "object": slot,
    }, "slots")


@require_POST
def slot_delete(request, pk):
    return _delete(request, get_object_or_404(Slot, pk=pk), "slot_list", "")


# --- Classes -----------------------------------------------------------------

def class_list(request):
    form = ClassForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        klass = form.save()
        messages.success(request, f"Added {klass}.")
        return redirect("class_detail", pk=klass.pk)
    classes = Class.objects.annotate(pupil_count=Count("pupils"))
    return _render(request, "timetable/class_list.html", {"form": form, "classes": classes}, "classes")


def class_detail(request, pk):
    klass = get_object_or_404(Class, pk=pk)
    is_details = request.method == "POST" and "save_details" in request.POST
    is_add = request.method == "POST" and "add_pupils" in request.POST
    form = ClassForm(request.POST if is_details else None, instance=klass)
    add_form = AddPupilsForm(request.POST if is_add else None, klass=klass)

    if is_details and form.is_valid():
        form.save()
        messages.success(request, "Class saved.")
        return redirect("class_detail", pk=klass.pk)

    if is_add and add_form.is_valid():
        new, skipped = parse_pupil_lines(add_form.cleaned_data["names"])
        ambiguous = []
        with transaction.atomic():
            for first_name, initial in new:
                # A pupil carried over from last year is reused, not made twice: the one current pupil
                # with this name, initial and (if the class has one) year group.
                same = Pupil.objects.filter(first_name__iexact=first_name, surname_initial__iexact=initial, left_on__isnull=True)
                if klass.year_group:
                    same = same.filter(year_group=klass.year_group)
                matches = list(same[:2])
                if len(matches) > 1:
                    ambiguous.append(f"{first_name} {initial}")
                    continue
                pupil = matches[0] if matches else Pupil.objects.create(
                    first_name=first_name, surname_initial=initial, year_group=klass.year_group)
                klass.pupils.add(pupil)
            klass.pupils.add(*add_form.cleaned_data["existing"])
        added = len(new) - len(ambiguous) + len(add_form.cleaned_data["existing"])
        messages.success(request, f"Added {added} pupil{'s' if added != 1 else ''}.")
        if skipped:
            messages.warning(request, "Skipped lines without a surname initial: " + "; ".join(skipped))
        if ambiguous:
            messages.warning(request, "More than one pupil matches, so choose them from Existing pupils: " + "; ".join(ambiguous))
        return redirect("class_detail", pk=klass.pk)

    return _render(request, "timetable/class_detail.html", {
        "klass": klass, "form": form, "add_form": add_form, "pupils": klass.pupils.all(),
    }, "classes")


@require_POST
def class_remove_pupil(request, pk, pupil_pk):
    klass = get_object_or_404(Class, pk=pk)
    pupil = get_object_or_404(Pupil, pk=pupil_pk)
    klass.pupils.remove(pupil)
    messages.success(request, f"Removed {pupil} from {klass}.")
    return redirect("class_detail", pk=klass.pk)


@require_POST
def class_delete(request, pk):
    return _delete(
        request, get_object_or_404(Class, pk=pk), "class_list",
        "This class has sessions. Delete its sessions first, or keep the class for history.",
    )


# --- Pupils ------------------------------------------------------------------

def pupil_list(request):
    form = PupilForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pupil = form.save()
        messages.success(request, f"Added {pupil}.")
        return redirect("pupil_list")
    year = request.GET.get("year")
    pupils = Pupil.objects.prefetch_related("classes")
    if year and year.isdigit():
        pupils = pupils.filter(year_group=int(year))
    years = Pupil.objects.exclude(year_group=None).values_list("year_group", flat=True).distinct().order_by("year_group")
    return _render(request, "timetable/pupil_list.html", {
        "form": form, "pupils": pupils, "years": years, "year": year,
    }, "pupils")


def pupil_edit(request, pk):
    pupil = get_object_or_404(Pupil, pk=pk)
    form = PupilForm(request.POST or None, instance=pupil)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved {pupil}.")
        return redirect("pupil_list")
    return _render(request, "timetable/object_form.html", {
        "form": form, "title": f"Edit {pupil}", "back": "pupil_list", "delete_url": "pupil_delete", "object": pupil,
    }, "pupils")


@require_POST
def pupil_delete(request, pk):
    return _delete(request, get_object_or_404(Pupil, pk=pk), "pupil_list", "")


# --- Sessions ----------------------------------------------------------------

def _parse_date(value, default):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


def session_list(request):
    timetable = Timetable.active()
    today = timezone.localdate()
    start = _parse_date(request.GET.get("from"), today - datetime.timedelta(days=today.weekday()))
    end = _parse_date(request.GET.get("to"), start + datetime.timedelta(days=13))

    is_add = request.method == "POST" and "add_session" in request.POST
    form = SessionForm(request.POST if is_add else None, timetable=timetable, initial={"date": today})
    if is_add and form.is_valid():
        session = form.save()
        messages.success(request, f"Added {session} on {session.date:%d/%m/%Y}.")
        return redirect("session_list")

    generate_form = GenerateSessionsForm(timetable=timetable, initial={"start": start, "end": end})
    sessions = Session.objects.filter(date__range=(start, end)).select_related("klass", "room")
    order = {p["label"]: i for i, p in enumerate(timetable.periods)}
    days = {}
    for session in sorted(sessions, key=lambda s: (s.date, order.get(s.period, len(order)), s.period)):
        days.setdefault(session.date, []).append(session)
    return _render(request, "timetable/session_list.html", {
        "form": form, "generate_form": generate_form, "days": days.items(), "start": start, "end": end,
    }, "sessions")


@require_POST
def session_generate(request):
    timetable = Timetable.active()
    form = GenerateSessionsForm(request.POST, timetable=timetable)
    if form.is_valid():
        data = form.cleaned_data
        created = generate_sessions(timetable, data["start"], data["end"], data.get("first_week", "A"))
        messages.success(request, f"Created {created} session{'s' if created != 1 else ''}.")
        return redirect(f"{reverse('session_list')}?from={data['start']}&to={data['end']}")
    for error in form.errors.values():
        messages.error(request, " ".join(error))
    return redirect("session_list")


def session_edit(request, pk):
    session = get_object_or_404(Session, pk=pk)
    form = SessionForm(request.POST or None, instance=session, timetable=Timetable.active())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved {session}.")
        return redirect(f"{reverse('session_list')}?from={session.date}")
    return _render(request, "timetable/object_form.html", {
        "form": form, "title": f"Edit {session} on {session.date:%d/%m/%Y}", "back": "session_list",
        "delete_url": "session_delete", "object": session,
    }, "sessions")


@require_POST
def session_delete(request, pk):
    return _delete(
        request, get_object_or_404(Session, pk=pk), "session_list",
        "This session has notes. Mark it cancelled instead, so the notes keep their lesson.",
    )
