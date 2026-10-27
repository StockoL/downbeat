"""Settings: the teacher's note types, weekly goals and lesson checklist."""

from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import redirect, render

from core.forms import NoteTypeForm

from .models import ChecklistItem, Goal, NoteType


class OrderedNoteTypeForm(NoteTypeForm):
    class Meta(NoteTypeForm.Meta):
        fields = ["order", "label", "icon", "is_house_point", "is_actionable_default"]
        widgets = {**NoteTypeForm.Meta.widgets, "order": forms.NumberInput(attrs={"min": 0, "max": 99})}


NoteTypeSettingsFormSet = forms.modelformset_factory(NoteType, form=OrderedNoteTypeForm, extra=2, can_delete=True)


def note_types(request):
    formset = NoteTypeSettingsFormSet(request.POST or None, queryset=NoteType.objects.all())
    if request.method == "POST" and formset.is_valid():
        try:
            with transaction.atomic():
                formset.save()
            messages.success(request, "Note types saved.")
        except ProtectedError:
            messages.error(request, "A note type that has been used can't be deleted, so its notes keep their meaning. Rename it instead.")
        return redirect("note_types")
    return render(request, "notes/note_types.html", {"nav": "settings", "section": "note_types", "formset": formset})


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ["text", "counts_note_type", "target_count", "scope", "klass", "week_start"]
        labels = {"counts_note_type": "Counts lessons with", "target_count": "Target", "week_start": "Starts"}
        widgets = {"week_start": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


GoalFormSet = forms.modelformset_factory(Goal, form=GoalForm, extra=1, can_delete=True)


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ["order", "text", "klass"]
        widgets = {"order": forms.NumberInput(attrs={"min": 0, "max": 99})}


ChecklistFormSet = forms.modelformset_factory(ChecklistItem, form=ChecklistItemForm, extra=2, can_delete=True)


def goals(request):
    formset = GoalFormSet(request.POST or None, queryset=Goal.objects.all())
    if request.method == "POST" and formset.is_valid():
        formset.save()
        messages.success(request, "Goals saved.")
        return redirect("goals")
    return render(request, "notes/goals.html", {"nav": "settings", "section": "goals", "formset": formset})


def checklist(request):
    formset = ChecklistFormSet(request.POST or None, queryset=ChecklistItem.objects.all())
    if request.method == "POST" and formset.is_valid():
        formset.save()
        messages.success(request, "Checklist saved.")
        return redirect("checklist")
    return render(request, "notes/checklist.html", {"nav": "settings", "section": "checklist", "formset": formset})
