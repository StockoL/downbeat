"""
Assembling a report comment from the teacher's own words: the comment bank's sentence for each
band they judged, then the pupil's latest feedback on what to develop. Nothing here judges; it
only puts the teacher's judgements and sentences in a row to be edited.
"""

import re

from django.db.models import Q

from assessment.models import Feedback

from .models import ReportSentence, SummativeJudgement

SECOND_OR_FIRST_PERSON = re.compile(r"\b(you|your|yours|yourself|I|I'm|I've|my|me)\b", re.IGNORECASE)


def judgements(pupil, units):
    return list(SummativeJudgement.objects.filter(pupil=pupil, unit__in=units).select_related("unit", "strand", "band")
                .order_by("unit__order", "strand__order"))


def assemble(pupil, units):
    """A first draft: one sentence per judgement (the unit's own sentence first, else a general one), then what to develop."""
    bank = list(ReportSentence.objects.filter(Q(unit__isnull=True) | Q(unit__in=units)))
    parts = []
    for j in judgements(pupil, units):
        matching = [s for s in bank if s.band_id == j.band_id and s.strand_id == j.strand_id]
        chosen = next((s for s in matching if s.unit_id == j.unit_id), None) or next((s for s in matching if s.unit_id is None), None)
        if chosen:
            parts.append(chosen.text.strip())
    latest = (Feedback.objects.filter(pupil=pupil, session__lesson__unit__in=units).exclude(develop="")
              .order_by("-created_at").first())
    if latest:
        parts.append(" ".join(p for p in (latest.develop.strip(), latest.how.strip()) if p))
    text = " ".join(parts)
    return text.replace("{name}", pupil.first_name)


def style_checks(text, style):
    """The house style as plain warnings, for the teacher to act on or ignore."""
    warnings = []
    if style.length_cap and len(text) > style.length_cap:
        warnings.append(f"{len(text)} characters: {len(text) - style.length_cap} over the limit of {style.length_cap}.")
    if style.third_person:
        found = sorted({m.group(0) for m in SECOND_OR_FIRST_PERSON.finditer(text)}, key=str.lower)
        if found:
            warnings.append("Not in the third person: " + ", ".join(f"“{w}”" for w in found) + ".")
    if "{name}" in text:
        warnings.append("{name} is still in the text.")
    return warnings
