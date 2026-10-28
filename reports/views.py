"""Pupils → class → Judgements: a band per strand per pupil, with the evidence and exemplars in view."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from assessment.feedback_views import units_taught
from assessment.models import Band, Observation, Strand
from timetable.models import Class

from .models import SummativeJudgement


def _choose(options, wanted):
    return next((o for o in options if str(o.pk) == wanted), options[0] if options else None)


def class_judgements(request, pk):
    """
    The judgement grid for one unit: each pupil, each strand the unit's components cover, the
    pupil's latest state on those components beside the band choices. No band is suggested.
    """
    klass = get_object_or_404(Class, pk=pk)
    units = units_taught(klass)
    unit = _choose(units, request.GET.get("unit") or request.POST.get("unit", ""))
    pupils = list(klass.pupils.all())
    bands = list(Band.objects.all())
    if unit is None or not bands:
        return render(request, "reports/judgements.html", {"nav": "pupils", "klass": klass, "unit": unit, "bands": bands})

    components = list(unit.components.select_related("strand"))
    strands = [s for s in Strand.objects.all() if any(c.strand_id == s.pk for c in components)]
    if request.method == "POST":
        _save(request, unit, pupils, strands, bands)
        messages.success(request, f"Judgements for {unit} saved.")
        return redirect(f"{reverse('class_judgements', args=[klass.pk])}?unit={unit.pk}")

    latest = {}
    for o in (Observation.objects.filter(pupil__in=pupils, component__in=components, assessor="teacher", deleted_at__isnull=True)
              .order_by("created_at")):
        latest[(o.pupil_id, o.component_id)] = o
    judged = {(j.pupil_id, j.strand_id): j for j in SummativeJudgement.objects.filter(unit=unit, pupil__in=pupils)}
    rows = []
    for pupil in pupils:
        cells = []
        for strand in strands:
            evidence = [(c, latest.get((pupil.pk, c.pk))) for c in components if c.strand_id == strand.pk]
            cells.append({"strand": strand, "evidence": evidence, "judgement": judged.get((pupil.pk, strand.pk))})
        rows.append({"pupil": pupil, "cells": cells})
    return render(request, "reports/judgements.html", {
        "nav": "pupils", "klass": klass, "units": units, "unit": unit, "bands": bands, "strands": strands, "rows": rows,
        "exemplars": unit.exemplars.select_related("component"),
    })


@transaction.atomic
def _save(request, unit, pupils, strands, bands):
    """Each band-<pupil>-<strand> chosen is kept with its note; one left blank removes the judgement."""
    by_id = {str(b.pk): b for b in bands}
    for pupil in pupils:
        for strand in strands:
            key = f"{pupil.pk}-{strand.pk}"
            band = by_id.get(request.POST.get(f"band-{key}", ""))
            note = request.POST.get(f"note-{key}", "").strip()[:300]
            existing = SummativeJudgement.objects.filter(pupil=pupil, unit=unit, strand=strand).first()
            if band is None:
                if existing:
                    existing.delete()
            elif existing is None:
                SummativeJudgement.objects.create(pupil=pupil, unit=unit, strand=strand, band=band, evidence_note=note)
            elif (existing.band_id, existing.evidence_note) != (band.pk, note):
                # Dated when it changes, so saving the grid again doesn't redate every judgement.
                existing.band, existing.evidence_note, existing.judged_at = band, note, timezone.localdate()
                existing.save()
