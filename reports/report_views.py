"""
Reports (desk): the house style and comment bank in Settings, a class's report comments drafted
from judgements and sentences, copied out one by one or exported as CSV, and promote-a-note.
Downbeat never writes to the school's systems: the only way out is the clipboard and a file.
"""

import csv

from django import forms
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from assessment.feedback_views import units_taught
from assessment.models import Strand
from notes.models import Note
from timetable.models import Class

from . import compose
from .models import ReportDraft, ReportSentence, ReportStyle

SentenceFormSet = forms.modelformset_factory(
    ReportSentence, fields=["strand", "band", "unit", "text"], extra=2, can_delete=True,
    widgets={"text": forms.Textarea(attrs={"rows": 2})},
)


class StyleForm(forms.ModelForm):
    class Meta:
        model = ReportStyle
        fields = ["length_cap", "third_person"]
        labels = {"length_cap": "Character limit", "third_person": "Check comments are in the third person"}


def report_settings(request):
    """The house style and the comment bank, both teacher-defined."""
    style = ReportStyle.current()
    data = request.POST if request.method == "POST" else None
    style_form = StyleForm(data, instance=style, prefix="style")
    sentences = SentenceFormSet(data, queryset=ReportSentence.objects.select_related("strand", "band", "unit"), prefix="sentences")
    if data is not None and style_form.is_valid() and sentences.is_valid():
        with transaction.atomic():
            style_form.save()
            sentences.save()
        messages.success(request, "Report settings saved.")
        return redirect("report_settings")
    return render(request, "reports/settings.html", {
        "nav": "settings", "section": "reports", "style_form": style_form, "sentences": sentences,
    })


def class_reports(request, pk):
    """Each pupil's comment: drafted from their judgements and feedback, edited and saved, then copied out."""
    klass = get_object_or_404(Class, pk=pk)
    units = units_taught(klass)
    if request.method == "POST":
        pupil = get_object_or_404(klass.pupils, pk=request.POST.get("pupil"))
        draft, _ = ReportDraft.objects.get_or_create(pupil=pupil, klass=klass)
        if "assemble" in request.POST:
            draft.text = compose.assemble(pupil, units)
            messages.success(request, f"Drafted {pupil}'s comment again from the comment bank.")
        else:
            draft.text = request.POST.get("text", "").strip()
            messages.success(request, f"Saved {pupil}'s comment.")
        draft.save()
        return redirect(f"{reverse('class_reports', args=[klass.pk])}#pupil-{pupil.pk}")

    style = ReportStyle.current()
    drafts = {d.pupil_id: d.text for d in ReportDraft.objects.filter(klass=klass)}
    rows = []
    for pupil in klass.pupils.all():
        saved = pupil.pk in drafts
        text = drafts[pupil.pk] if saved else compose.assemble(pupil, units)
        rows.append({
            "pupil": pupil, "text": text, "saved": saved, "judgements": compose.judgements(pupil, units),
            "warnings": compose.style_checks(text, style),
        })
    return render(request, "reports/class_reports.html", {
        "nav": "pupils", "klass": klass, "rows": rows, "style": style, "has_bank": ReportSentence.objects.exists(),
    })


def reports_csv(request, pk):
    """Name, UPN, a band per unit and strand, and the comment: for entering in the school system by hand or import."""
    klass = get_object_or_404(Class, pk=pk)
    units = units_taught(klass)
    drafts = {d.pupil_id: d.text for d in ReportDraft.objects.filter(klass=klass)}
    pupils = list(klass.pupils.all())
    judged = {p.pk: {(j.unit_id, j.strand_id): j.band.name for j in compose.judgements(p, units)} for p in pupils}
    columns = sorted({key for bands in judged.values() for key in bands}, key=lambda k: (str(k[0]), str(k[1])))
    names = {u.pk: u.name for u in units}
    strands = {s.pk: s.name for s in Strand.objects.all()}
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="reports-{slugify(klass.name)}-{timezone.localdate():%Y-%m-%d}.csv"'
    response.write("﻿")  # so Excel reads the file as UTF-8
    writer = csv.writer(response)
    writer.writerow(["Name", "UPN", *[f"{names.get(u, '')}: {strands.get(s, '')}" for u, s in columns], "Comment"])
    for pupil in pupils:
        text = drafts.get(pupil.pk) or compose.assemble(pupil, units)
        writer.writerow([str(pupil), pupil.upn, *[judged[pupil.pk].get(key, "") for key in columns], text])
    return response


@require_POST
def note_promote(request, pk):
    """The one door from the private notes to the school's system: its text was copied, so mark it promoted."""
    note = get_object_or_404(Note, pk=pk)
    if note.promoted_to_mis_at is None:
        Note.objects.filter(pk=note.pk).update(promoted_to_mis_at=timezone.now())
    messages.success(request, "Copied. Paste it into the school system; it is marked as promoted here.")
    return redirect(f"{reverse('pupil_page', args=[note.pupil_id])}#notes" if note.pupil_id else "pupils_home")
