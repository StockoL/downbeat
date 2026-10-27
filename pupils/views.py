"""
The Pupils area (desk, any time): classes, a class list, and the pupil page. The pupil page is
the only place a flag's label is ever shown.
"""

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from timetable.models import Class, Pupil

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
    return render(request, "pupils/class.html", {
        "nav": "pupils", "klass": klass, "rows": [{"pupil": p, "flags": colours.get(p.pk, [])} for p in pupils],
    })


def pupil_page(request, pk):
    pupil = get_object_or_404(Pupil, pk=pk)
    adding_flag = request.method == "POST" and "add_flag" in request.POST
    adding_relationship = request.method == "POST" and "add_relationship" in request.POST
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
    return render(request, "pupils/pupil.html", {
        "nav": "pupils",
        "pupil": pupil,
        "classes": pupil.classes.all(),
        "flags": pupil.flags.select_related("flag_type"),
        "flag_form": form if form.fields["flag_type"].queryset.exists() else None,
        "relationships": [{"r": r, "other": r.other(pupil)} for r in Relationship.involving(pupil)],
        "relationship_form": relationship_form if relationship_form.fields["other"].queryset.exists() else None,
        "notes": notes,
    })


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
