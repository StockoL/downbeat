"""Settings → strands and bands; Plan → a unit's components and feedback codes."""

import json
import uuid

from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from plans.models import LessonPlan, Unit

from . import criteria
from .models import Band, Check, Component, FeedbackCode, Strand

StrandFormSet = forms.modelformset_factory(
    Strand, fields=["order", "name"], extra=2, can_delete=True,
    widgets={"order": forms.NumberInput(attrs={"min": 0, "max": 99})},
)
BandFormSet = forms.modelformset_factory(
    Band, fields=["order", "name", "description"], extra=2, can_delete=True,
    widgets={"order": forms.NumberInput(attrs={"min": 0, "max": 99}), "description": forms.TextInput()},
)


def _settings_formset(request, formset_class, template, section, name):
    formset = formset_class(request.POST or None, queryset=formset_class.model.objects.all())
    if request.method == "POST" and formset.is_valid():
        try:
            with transaction.atomic():
                formset.save()
            messages.success(request, f"{name} saved.")
        except ProtectedError:
            messages.error(request, f"A {name.lower()[:-1]} still in use can't be deleted.")
        return redirect(section)
    return render(request, template, {"nav": "settings", "section": section, "formset": formset})


def strands(request):
    return _settings_formset(request, StrandFormSet, "assessment/strands.html", "strands", "Strands")


def bands(request):
    return _settings_formset(request, BandFormSet, "assessment/bands.html", "bands", "Bands")


class ComponentForm(forms.ModelForm):
    class Meta:
        model = Component
        fields = ["order", "text", "strand", "next_step_default", "cumulative_of"]
        labels = {"next_step_default": "Default next step", "cumulative_of": "Builds on"}
        widgets = {"order": forms.NumberInput(attrs={"min": 0, "max": 99})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        unit = self.instance.unit if self.instance.unit_id else None
        self.fields["cumulative_of"].queryset = unit.components.exclude(pk=self.instance.pk) if unit else Component.objects.none()


ComponentFormSet = forms.inlineformset_factory(Unit, Component, form=ComponentForm, extra=2, can_delete=True)
CodeFormSet = forms.inlineformset_factory(
    Unit, FeedbackCode, fields=["number", "text", "component", "action"], extra=2, can_delete=True,
    widgets={"number": forms.NumberInput(attrs={"min": 1, "max": 99})},
)


def unit_assessment(request, pk):
    """The unit's components (three to six, pupil-facing) and its numbered feedback codes."""
    unit = get_object_or_404(Unit.objects.select_related("scheme"), pk=pk)
    data = request.POST if request.method == "POST" else None
    components = ComponentFormSet(data, instance=unit, prefix="components")
    for form in components.forms:
        form.instance.unit = unit
        form.fields["cumulative_of"].queryset = unit.components.exclude(pk=form.instance.pk)
    codes = CodeFormSet(data, instance=unit, prefix="codes")
    for form in codes.forms:
        form.fields["component"].queryset = unit.components.all()
    if data is not None and components.is_valid() and codes.is_valid():
        with transaction.atomic():
            components.save()
            codes.save()
        messages.success(request, "Saved.")
        return redirect("unit_assessment", pk=unit.pk)
    return render(request, "assessment/unit.html", {
        "nav": "plan", "unit": unit, "components": components, "codes": codes, "has_strands": Strand.objects.exists(),
        "checks": Check.objects.filter(lesson_plan__unit=unit).select_related("lesson_plan").order_by("lesson_plan__order"),
    })


def components_export(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    response = HttpResponse(json.dumps(criteria.export(unit), indent=2), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="criteria-{slugify(unit.name)}.json"'
    return response


@require_POST
def components_import(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    upload = request.FILES.get("file")
    if upload is None or upload.size > 200_000:
        messages.error(request, "Choose a criteria file (a small .json).")
        return redirect("unit_assessment", pk=unit.pk)
    try:
        added, codes = criteria.import_into(unit, upload.read())
    except criteria.BadCriteria as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Added {added} component{'s' if added != 1 else ''} and {codes} feedback code{'s' if codes != 1 else ''}.")
    return redirect("unit_assessment", pk=unit.pk)


@require_POST
def hinge_copy(request, pk):
    """Starts a lesson's hinge check from one in the bank, replacing any it had."""
    lesson = get_object_or_404(LessonPlan, pk=pk)
    try:
        source_id = uuid.UUID(request.POST.get("from", ""))
    except ValueError:
        source_id = None
    source = get_object_or_404(Check, pk=source_id, lesson_plan__isnull=False)
    Check.objects.update_or_create(lesson_plan=lesson, defaults={
        "question": source.question, "answer": source.answer, "distractors": source.distractors, "threshold": source.threshold,
    })
    messages.success(request, f"Copied the hinge check from L{source.lesson_plan.order}. Change it below if this lesson needs it different.")
    return redirect(reverse("lesson", args=[lesson.pk]) + "#hinge")
