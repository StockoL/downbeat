"""Settings: the teacher's note types."""

from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import redirect, render

from core.forms import NoteTypeForm

from .models import NoteType


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
