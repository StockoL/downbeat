"""Plan (desk, ahead): schemes, units, lessons, and which lesson each session will teach."""

import datetime

from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from assessment.forms import HingeForm
from assessment.models import Check
from timetable.models import Class, Session

from . import services
from .forms import ActivityFormSet, LessonForm, ResourceFormSet, SchemeForm, UnitForm
from .models import LessonPlan, Scheme, Unit


def _render(request, template, context):
    return render(request, template, {"nav": "plan", **context})


def schemes(request):
    form = SchemeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        scheme = form.save()
        return redirect("scheme", pk=scheme.pk)
    return _render(request, "plans/schemes.html", {"schemes": Scheme.objects.prefetch_related("units"), "form": form})


def scheme(request, pk):
    scheme = get_object_or_404(Scheme, pk=pk)
    form = UnitForm(request.POST or None, initial={"order": scheme.units.count() + 1})
    if request.method == "POST" and form.is_valid():
        unit = form.save(commit=False)
        unit.scheme = scheme
        unit.save()
        return redirect("unit", pk=unit.pk)
    return _render(request, "plans/scheme.html", {"scheme": scheme, "units": scheme.units.all(), "form": form})


def unit(request, pk):
    unit = get_object_or_404(Unit.objects.select_related("scheme"), pk=pk)
    form = UnitForm(request.POST or None, instance=unit)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Unit saved.")
        return redirect("unit", pk=unit.pk)
    return _render(request, "plans/unit.html", {
        "unit": unit, "form": form, "lessons": unit.lessons.prefetch_related("activities", "resources"),
    })


@require_POST
def unit_add_lesson(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    lesson = LessonPlan.objects.create(unit=unit, order=unit.lessons.count() + 1, objective="New lesson")
    return redirect("lesson", pk=lesson.pk)


@require_POST
def unit_duplicate(request, pk):
    copy = services.duplicate_unit(get_object_or_404(Unit, pk=pk))
    messages.success(request, f"Made {copy}, with every lesson, activity and resource.")
    return redirect("unit", pk=copy.pk)


@require_POST
def unit_delete(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    scheme_pk = unit.scheme_id
    try:
        unit.delete()
    except ProtectedError:
        messages.error(request, f"{unit} has observations or judgements recorded against it, so it is kept: they are part of "
                                "pupils' records. Its lessons and components can still be changed.")
        return redirect("unit", pk=unit.pk)
    messages.success(request, f"Deleted {unit}. Sessions that taught it keep their notes.")
    return redirect("scheme", pk=scheme_pk)


def lesson(request, pk):
    """The lesson editor: a structured form, activities as an ordered list, resources with a print flag."""
    lesson = get_object_or_404(LessonPlan.objects.select_related("unit__scheme"), pk=pk)
    data = request.POST if request.method == "POST" else None
    form = LessonForm(data, instance=lesson)
    activities = ActivityFormSet(data, instance=lesson, prefix="activities")
    resources = ResourceFormSet(data, instance=lesson, prefix="resources")
    hinge = HingeForm(data, prefix="hinge", check=lesson.checks.first())
    if data is not None and all([form.is_valid(), activities.is_valid(), resources.is_valid(), hinge.is_valid()]):
        with transaction.atomic():
            form.save()
            activities.save()
            resources.save()
            hinge.save(lesson)
        messages.success(request, "Lesson saved.")
        return redirect("lesson", pk=lesson.pk)
    total = sum(a.minutes for a in lesson.activities.all())
    # The unit's other lessons' checks: the bank to start this one from.
    bank = Check.objects.filter(lesson_plan__unit=lesson.unit).exclude(lesson_plan=lesson).select_related("lesson_plan")
    return _render(request, "plans/lesson.html", {
        "lesson": lesson, "form": form, "activities": activities, "resources": resources, "total_minutes": total,
        "hinge": hinge, "bank": bank,
    })


@require_POST
def lesson_delete(request, pk):
    lesson = get_object_or_404(LessonPlan, pk=pk)
    unit_pk = lesson.unit_id
    lesson.delete()
    return redirect("unit", pk=unit_pk)


def class_lessons(request, pk):
    """Plan → class → Lessons: which lesson each coming session will teach."""
    klass = get_object_or_404(Class, pk=pk)
    today = timezone.localdate()
    sessions = list(
        Session.objects.filter(klass=klass, date__gte=today - datetime.timedelta(days=7), date__lte=today + datetime.timedelta(weeks=6))
        .select_related("lesson__unit").order_by("date", "period")
    )
    units = Unit.objects.select_related("scheme").prefetch_related("lessons")
    return _render(request, "plans/class_lessons.html", {
        "klass": klass, "sessions": sessions, "units": units, "today": today,
    })


@require_POST
def session_set_lesson(request, pk):
    session = get_object_or_404(Session, pk=pk)
    lesson_id = request.POST.get("lesson")
    session.lesson = get_object_or_404(LessonPlan, pk=lesson_id) if lesson_id else None
    session.save(update_fields=["lesson", "updated_at"])
    return redirect("class_lessons", pk=session.klass_id)


@require_POST
def class_fill(request, pk):
    klass = get_object_or_404(Class, pk=pk)
    unit = get_object_or_404(Unit, pk=request.POST.get("unit"))
    filled = services.fill_from_unit(klass, unit)
    messages.success(request, f"Planned {filled} lesson{'s' if filled != 1 else ''} from {unit}.")
    return redirect("class_lessons", pk=klass.pk)
