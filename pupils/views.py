"""
The Pupils area (desk, any time): classes, a class list, and the pupil page. The pupil page is
the only place a flag's label is ever shown.
"""

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from assessment.forms import FeedbackForm, RecordingForm
from assessment.models import Feedback
from core.data import export_pupil
from timetable.models import Class, Pupil, SessionAttendance

from .forms import FlagTypeFormSet, PupilFlagForm, RelationshipForm
from .models import FlagType, PupilFlag, Relationship
from .services import flag_colours


def pupils_home(request):
    classes = Class.objects.annotate(pupil_count=Count("pupils"))
    return render(request, "pupils/home.html", {"nav": "pupils", "classes": classes})


def class_pupils(request, pk):
    klass = get_object_or_404(Class, pk=pk)
    pupils = list(klass.pupils.all())
    colours = flag_colours([p.pk for p in pupils])
    attendance = {}
    if klass.kind == Class.CO_CURRICULAR:
        # Ensemble attendance: of the rehearsals where the register was taken, how many each came to.
        for pupil_id, present in SessionAttendance.objects.filter(session__klass=klass).values_list("pupil_id", "present"):
            came, marked = attendance.get(pupil_id, (0, 0))
            attendance[pupil_id] = (came + present, marked + 1)
    return render(request, "pupils/class.html", {
        "nav": "pupils", "klass": klass,
        "rows": [{"pupil": p, "flags": colours.get(p.pk, []), "attendance": attendance.get(p.pk)} for p in pupils],
    })


def pupil_page(request, pk):
    pupil = get_object_or_404(Pupil, pk=pk)
    adding_flag = request.method == "POST" and "add_flag" in request.POST
    adding_relationship = request.method == "POST" and "add_relationship" in request.POST
    adding_feedback = request.method == "POST" and "add_feedback" in request.POST
    adding_recording = request.method == "POST" and "add_recording" in request.POST
    recording_form = RecordingForm(request.POST if adding_recording else None, pupil=pupil, prefix="recording")
    if adding_recording and recording_form.is_valid():
        recording_form.save()
        messages.success(request, "Recording added to the timeline.")
        return redirect(f"{reverse('pupil_page', args=[pupil.pk])}#timeline")
    feedback_form = FeedbackForm(request.POST if adding_feedback else None, pupil=pupil, prefix="feedback")
    if adding_feedback and feedback_form.is_valid():
        feedback_form.save()
        messages.success(request, "Feedback saved.")
        return redirect(f"{reverse('pupil_page', args=[pupil.pk])}#feedback")
    form = PupilFlagForm(request.POST if adding_flag else None, pupil=pupil)
    relationship_form = RelationshipForm(request.POST if adding_relationship else None, pupil=pupil)
    if adding_flag and form.is_valid():
        form.save()
        messages.success(request, "Flag added.")
        return redirect("pupil_page", pk=pupil.pk)
    if adding_relationship and relationship_form.is_valid():
        relationship_form.save()
        messages.success(request, "Saved.")
        return redirect("pupil_page", pk=pupil.pk)
    notes = pupil.notes.live().select_related("note_type", "session__klass").order_by("-created_at")[:100]
    groups = pupil.group_memberships.values_list("group_id", flat=True)
    feedback = (Feedback.objects.filter(Q(pupil=pupil) | Q(group__in=groups))
                .select_related("session__klass", "group", "component").order_by("-created_at")[:50])
    observations = (pupil.observations.filter(deleted_at__isnull=True)
                    .select_related("component", "session__klass").order_by("-created_at")[:50])
    return render(request, "pupils/pupil.html", {
        "nav": "pupils",
        "pupil": pupil,
        "classes": pupil.classes.all(),
        "flags": pupil.flags.select_related("flag_type"),
        "flag_form": form if form.fields["flag_type"].queryset.exists() else None,
        "relationships": [{"r": r, "other": r.other(pupil)} for r in Relationship.involving(pupil)],
        "relationship_form": relationship_form if relationship_form.fields["other"].queryset.exists() else None,
        "notes": notes,
        "feedback": feedback,
        "feedback_form": feedback_form if feedback_form.fields["lesson"].queryset.exists() else None,
        "feedback_open": adding_feedback,
        "timeline": timeline(pupil, groups),
        "recording_form": recording_form if pupil.recording_permitted and recording_form.fields["lesson"].queryset.exists() else None,
        "recording_open": adding_recording,
        "observations": observations,
        "judgements": pupil.judgements.select_related("unit", "strand", "band").order_by("-judged_at"),
        "loans": pupil.loans.filter(returned_at__isnull=True).select_related("item"),
    })


def timeline(pupil, groups):
    """
    The ipsative timeline: the pupil's recordings, oldest first, one line per component (the same
    piece of work), each with what was observed or said at that point. Compared with themselves only.
    """
    lines = {}
    for o in pupil.observations.filter(deleted_at__isnull=True).exclude(recording_path="").select_related("component", "session"):
        lines.setdefault(o.component, []).append({
            "date": o.session.date, "state": o.get_state_display(), "said": o.next_step and f"Next: {o.next_step}",
            "path": o.recording_path, "seconds": None, "assessor": o.assessor,
        })
    for f in (Feedback.objects.filter(Q(pupil=pupil) | Q(group__in=groups)).exclude(recording_path="")
              .select_related("component", "session", "group")):
        lines.setdefault(f.component, []).append({
            "date": f.session.date, "state": "", "said": f.develop or f.done_well or f.how,
            "path": f.recording_path, "seconds": f.recording_seconds, "group": f.group,
        })
    ordered = sorted(lines.items(), key=lambda item: (item[0] is None, str(item[0])))
    return [{"component": component, "points": sorted(points, key=lambda p: p["date"])} for component, points in ordered]


def pupil_export(request, pk):
    """Everything held about this pupil, as one JSON file: the answer to a subject access request."""
    pupil = get_object_or_404(Pupil, pk=pk)
    response = HttpResponse(export_pupil(pupil), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="downbeat-{slugify(str(pupil))}-{timezone.localdate():%Y-%m-%d}.json"'
    return response


@require_POST
def pupil_flag_remove(request, pk):
    flag = get_object_or_404(PupilFlag.objects.select_related("pupil"), pk=pk)
    flag.delete()
    messages.success(request, "Flag removed.")
    return redirect("pupil_page", pk=flag.pupil.pk)


@require_POST
def relationship_remove(request, pk, pupil_pk):
    get_object_or_404(Relationship, pk=pk).delete()
    messages.success(request, "Removed.")
    return redirect("pupil_page", pk=pupil_pk)


def flag_types(request):
    """Settings → Flags."""
    formset = FlagTypeFormSet(request.POST or None, queryset=FlagType.objects.all())
    if request.method == "POST" and formset.is_valid():
        try:
            with transaction.atomic():
                formset.save()
            messages.success(request, "Flags saved.")
        except ProtectedError:
            messages.error(request, "A flag that pupils still have can't be deleted. Remove it from them first.")
        return redirect("flag_types")
    return render(request, "pupils/flag_types.html", {
        "nav": "settings", "section": "flags", "formset": formset, "palette": range(1, 9),
    })
