"""
Feedback (desk): three-part feedback per lesson, the unit's codes as a slide, the class-by-component
view, and self- and peer-assessment entered in one go from the class list.
"""

import uuid

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from plans.models import Unit
from timetable.models import Class, Session

from .forms import FeedbackForm
from .models import Component, Feedback, Observation


def session_feedback(request, pk):
    """A lesson's feedback: write it for a pupil or a group, and see what's been written."""
    session = get_object_or_404(Session.objects.select_related("klass", "lesson__unit"), pk=pk)
    form = FeedbackForm(request.POST or None, session=session)
    if request.method == "POST" and form.is_valid():
        feedback = form.save()
        messages.success(request, f"Feedback saved for {feedback.pupil or feedback.group}.")
        return redirect("session_feedback", pk=session.pk)
    return render(request, "assessment/feedback.html", {
        "nav": "sweep", "session": session, "form": form,
        "feedback": session.feedback.select_related("pupil", "group", "component"),
    })


@require_POST
def feedback_delete(request, pk):
    feedback = get_object_or_404(Feedback, pk=pk)
    feedback.delete()
    messages.success(request, "Feedback deleted.")
    return redirect("session_feedback", pk=feedback.session_id)


def codes_slide(request, pk):
    """The unit's numbered feedback codes, large, black on white: a slide for the whole class."""
    unit = get_object_or_404(Unit, pk=pk)
    return render(request, "assessment/codes_slide.html", {"unit": unit, "codes": unit.feedback_codes.all()})


def _units_taught(klass):
    """Units with components that this class has had a lesson from, most recent first."""
    seen = []
    sessions = Session.objects.filter(klass=klass, lesson__unit__components__isnull=False).exclude(status=Session.CANCELLED)
    for unit_id in sessions.order_by("-date").values_list("lesson__unit_id", flat=True):
        if unit_id not in seen:
            seen.append(unit_id)
    units = Unit.objects.in_bulk(seen)
    return [units[pk] for pk in seen]


def _chosen(request, options, key):
    """The option whose pk is in the query string, else the first; None when there are none."""
    wanted = request.GET.get(key, "")
    return next((o for o in options if str(o.pk) == wanted), options[0] if options else None)


def class_components(request, pk):
    """
    Each pupil's latest state on each of a unit's components: states only, never a total or a
    percentage, so it shows where the class is not yet secure without turning it into a score.
    """
    klass = get_object_or_404(Class, pk=pk)
    units = _units_taught(klass)
    unit = _chosen(request, units, "unit")
    assessor = request.GET.get("assessor") if request.GET.get("assessor") in dict(Observation.ASSESSORS) else "teacher"
    components = list(unit.components.all()) if unit else []
    latest = {}
    for o in (Observation.objects.filter(pupil__classes=klass, component__in=components, assessor=assessor, deleted_at__isnull=True)
              .order_by("created_at")):
        latest[(o.pupil_id, o.component_id)] = o
    rows = [{"pupil": p, "cells": [latest.get((p.pk, c.pk)) for c in components]} for p in klass.pupils.all()]
    return render(request, "assessment/class_components.html", {
        "nav": "pupils", "klass": klass, "units": units, "unit": unit, "components": components, "rows": rows,
        "assessor": assessor, "assessors": Observation.ASSESSORS,
    })


def class_self_peer(request, pk):
    """Self- or peer-assessment for the whole class against one component, entered from the class list."""
    klass = get_object_or_404(Class, pk=pk)
    sessions = list(
        Session.objects.filter(klass=klass, date__lte=timezone.localdate(), lesson__unit__components__isnull=False)
        .exclude(status=Session.CANCELLED).select_related("lesson__unit").distinct().order_by("-date", "-period")[:20]
    )
    session = _chosen(request, sessions, "session")
    if request.method == "POST":
        return _save_self_peer(request, klass, sessions)
    return render(request, "assessment/self_peer.html", {
        "nav": "pupils", "klass": klass, "sessions": sessions, "session": session,
        "components": session.lesson.unit.components.all() if session else [],
        "assessors": [a for a in Observation.ASSESSORS if a[0] != "teacher"],
        "states": Observation.STATES, "pupils": klass.pupils.all(),
    })


def _save_self_peer(request, klass, sessions):
    try:
        session = next(s for s in sessions if s.pk == uuid.UUID(request.POST.get("session", "")))
        component = session.lesson.unit.components.get(pk=uuid.UUID(request.POST.get("component", "")))
    except (StopIteration, ValueError, Component.DoesNotExist):
        messages.error(request, "Choose a lesson and one of its unit's components.")
        return redirect("class_self_peer", pk=klass.pk)
    assessor = request.POST.get("assessor")
    if assessor not in ("self", "peer"):
        messages.error(request, "Choose self or peer.")
        return redirect("class_self_peer", pk=klass.pk)
    states = dict(Observation.STATES)
    made = 0
    with transaction.atomic():
        for pupil in klass.pupils.all():
            state = request.POST.get(f"state-{pupil.pk}")
            if state in states:
                # The component's next step is attached, as it is for the teacher's own (rule 4).
                Observation.objects.create(session=session, pupil=pupil, component=component, state=state,
                                           assessor=assessor, next_step=component.next_step_default)
                made += 1
    word = "self-assessment" if assessor == "self" else "peer assessment"
    messages.success(request, f"Saved {made} {word}{'s' if made != 1 else ''} for {component}.")
    return redirect(f"{request.path}?session={session.pk}")
