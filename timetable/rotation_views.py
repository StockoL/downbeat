"""Settings → Rotations: the instrumental timetable, generated or pasted from a spreadsheet."""

import datetime

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import DATE
from .models import Pupil, PupilRotation, Rotation, Slot, Timetable
from .rotations import BadSchedule, describe, parse_schedule, rotating


def _periods():
    return [p["label"] for p in Timetable.active().periods]


class GenerateForm(forms.Form):
    name = forms.CharField(max_length=60, help_text="E.g. the instrumental teacher and instrument.")
    day = forms.TypedChoiceField(choices=Slot.DAYS, coerce=int)
    periods = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, help_text="The periods the lessons rotate through.")
    first_week = forms.DateField(widget=DATE, label="From the week of")
    weeks = forms.IntegerField(min_value=1, max_value=52, initial=14, label="For how many weeks")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["periods"].choices = [(p, p) for p in _periods()]


class ImportForm(forms.Form):
    name = forms.CharField(max_length=60)
    schedule = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8, "placeholder": "02/11/2026, Tue P1, Tue P2, Tue P3\n09/11/2026, Tue P2, Tue P3, Tue P1"}),
        help_text="One row per week: the week's date, then each slot as a day and a period. Paste from a spreadsheet.",
    )

    def clean(self):
        data = super().clean()
        if data.get("schedule"):
            try:
                data["weeks"], data["slots"] = parse_schedule(data["schedule"], set(_periods()))
            except BadSchedule as error:
                self.add_error("schedule", str(error))
        return data


def rotation_list(request):
    action = request.POST.get("action") if request.method == "POST" else None
    generate = GenerateForm(request.POST if action == "generate" else None, prefix="gen",
                            initial={"first_week": timezone.localdate()})
    paste = ImportForm(request.POST if action == "import" else None, prefix="imp")
    if action == "generate" and generate.is_valid():
        data = generate.cleaned_data
        periods = [p for p in _periods() if p in data["periods"]]  # in timetable order
        weeks, slots = rotating(data["day"], periods, data["first_week"], data["weeks"])
        rotation = Rotation.objects.create(name=data["name"], slot_count=len(periods), weeks=weeks, slots=slots)
        return redirect("rotation_detail", pk=rotation.pk)
    if action == "import" and paste.is_valid():
        data = paste.cleaned_data
        rotation = Rotation.objects.create(name=data["name"], slot_count=len(data["slots"][0]), weeks=data["weeks"], slots=data["slots"])
        return redirect("rotation_detail", pk=rotation.pk)
    return render(request, "timetable/rotations.html", {
        "nav": "settings", "section": "rotations", "rotations": Rotation.objects.all(), "generate": generate, "paste": paste,
    })


class AssignForm(forms.Form):
    pupil = forms.ModelChoiceField(queryset=Pupil.objects.none())
    slot_index = forms.TypedChoiceField(coerce=int, label="Slot")

    def __init__(self, *args, rotation, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pupil"].queryset = Pupil.objects.exclude(rotations__rotation=rotation)
        self.fields["slot_index"].choices = [(i, f"Slot {i + 1}") for i in range(rotation.slot_count)]


def rotation_detail(request, pk):
    rotation = get_object_or_404(Rotation, pk=pk)
    form = AssignForm(request.POST or None, rotation=rotation)
    if request.method == "POST" and form.is_valid():
        PupilRotation.objects.create(rotation=rotation, **form.cleaned_data)
        return redirect("rotation_detail", pk=rotation.pk)
    assigned = list(rotation.pupils.select_related("pupil"))
    return render(request, "timetable/rotation.html", {
        "nav": "settings", "section": "rotations", "rotation": rotation, "form": form,
        "grid": [
            {"week": datetime.date.fromisoformat(week), "cells": [describe(day, period) for day, period in row]}
            for week, row in zip(rotation.weeks, rotation.slots, strict=True)
        ],
        "by_slot": [
            {"slot": i + 1, "entries": [e for e in assigned if e.slot_index == i]} for i in range(rotation.slot_count)
        ],
    })


@require_POST
def rotation_unassign(request, pk):
    entry = get_object_or_404(PupilRotation, pk=pk)
    entry.delete()
    return redirect("rotation_detail", pk=entry.rotation_id)


@require_POST
def rotation_delete(request, pk):
    rotation = get_object_or_404(Rotation, pk=pk)
    rotation.delete()
    messages.success(request, f"Deleted {rotation}.")
    return redirect("rotation_list")
