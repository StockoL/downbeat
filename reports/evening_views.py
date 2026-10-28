"""Pupils → Parents' evenings: define an evening, book families, and run the night from the iPad."""

import datetime

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from timetable.models import Class, Pupil

from . import evenings
from .models import EveningSlot, ParentsEvening

TIME = forms.TimeInput(attrs={"type": "time"})


class EveningForm(forms.ModelForm):
    breaks = forms.CharField(required=False, label="Breaks", help_text="Times with no appointments, e.g. 18:00-18:15, 19:30-19:40.")

    class Meta:
        model = ParentsEvening
        fields = ["name", "date", "start", "end", "slot_minutes", "location"]
        labels = {"slot_minutes": "Minutes per family"}
        widgets = {"date": forms.DateInput(attrs={"type": "date"}), "start": TIME, "end": TIME,
                   "slot_minutes": forms.NumberInput(attrs={"min": 2, "max": 30})}

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["end"] <= data["start"]:
            self.add_error("end", "The evening ends after it starts.")
        spans = []
        for part in filter(None, (p.strip() for p in data.get("breaks", "").split(","))):
            try:
                start, end = (datetime.time.fromisoformat(t.strip()) for t in part.split("-"))
                spans.append([f"{start:%H:%M}", f"{end:%H:%M}"])
            except ValueError:
                self.add_error("breaks", f"“{part}” isn't a time range like 18:00-18:15.")
        data["break_times"] = spans
        return data

    def save(self, commit=True):
        self.instance.break_times = self.cleaned_data["break_times"]
        return super().save(commit)


def evening_list(request):
    form = EveningForm(request.POST or None, initial={"slot_minutes": 5})
    if request.method == "POST" and form.is_valid():
        evening = form.save()
        made = evenings.generate_slots(evening)
        messages.success(request, f"{evening}: {made} slots.")
        return redirect("evening", pk=evening.pk)
    return render(request, "reports/evenings.html", {"nav": "pupils", "evenings": ParentsEvening.objects.all(), "form": form})


def evening(request, pk):
    """The evening at the desk: every slot, a booking form, the school's CSV, and the way to the night."""
    evening = get_object_or_404(ParentsEvening, pk=pk)
    slots = list(evening.slots.select_related("pupil"))
    booked = {s.pupil_id for s in slots if s.pupil_id}
    classes = [(c, [p for p in c.pupils.all() if p.pk not in booked]) for c in Class.objects.prefetch_related("pupils")]
    return render(request, "reports/evening.html", {
        "nav": "pupils", "evening": evening, "slots": slots, "free": [s for s in slots if s.pupil_id is None],
        "classes": [(c, pupils) for c, pupils in classes if pupils],
    })


def _local(request, url):
    """A return address only if it stays on this site."""
    return url if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}) else None


def _slot(evening, pk):
    return get_object_or_404(EveningSlot, evening=evening, pk=pk)


@require_POST
def evening_book(request, pk):
    evening = get_object_or_404(ParentsEvening, pk=pk)
    slot = _slot(evening, request.POST.get("slot"))
    pupil = get_object_or_404(Pupil, pk=request.POST.get("pupil"))
    try:
        evenings.book(slot, pupil)
        messages.success(request, f"{pupil}'s family at {slot.start_time:%H:%M}.")
    except evenings.Refused as error:
        messages.error(request, str(error))
    return redirect(_local(request, request.POST.get("next")) or reverse("evening", args=[evening.pk]))


@require_POST
def evening_unbook(request, pk, slot_pk):
    evening = get_object_or_404(ParentsEvening, pk=pk)
    slot = _slot(evening, slot_pk)
    evenings.unbook(slot)
    messages.success(request, f"{slot.start_time:%H:%M} is free again.")
    return redirect("evening", pk=evening.pk)


@require_POST
def evening_import(request, pk):
    evening = get_object_or_404(ParentsEvening, pk=pk)
    upload = request.FILES.get("file")
    text = upload.read().decode("utf-8-sig", errors="replace") if upload and upload.size < 200_000 else request.POST.get("text", "")
    booked, problems = evenings.import_bookings(evening, text)
    messages.success(request, f"Booked {booked} from the file.")
    for problem in problems[:20]:
        messages.error(request, problem)
    return redirect("evening", pk=evening.pk)


@require_POST
def evening_delete(request, pk):
    evening = get_object_or_404(ParentsEvening, pk=pk)
    evening.delete()
    messages.success(request, f"Deleted {evening}.")
    return redirect("evening_list")


def tonight(request, pk):
    """On the night, on the iPad: each family in time order, their pupil a tap away, attended or not, a note."""
    evening = get_object_or_404(ParentsEvening, pk=pk)
    now = timezone.localtime().time() if evening.date == timezone.localdate() else None
    slots = [s for s in evening.slots.select_related("pupil") if s.pupil_id]
    current = next((s for s in slots if now and s.start_time >= now.replace(second=0, microsecond=0)), None)
    return render(request, "reports/tonight.html", {"nav": "pupils", "evening": evening, "slots": slots, "current": current})


@require_POST
def tonight_mark(request, pk, slot_pk):
    evening = get_object_or_404(ParentsEvening, pk=pk)
    slot = _slot(evening, slot_pk)
    if "note" in request.POST:
        slot.on_the_night_note = request.POST["note"].strip()
        slot.save(update_fields=["on_the_night_note", "updated_at"])
    else:
        choice = {"yes": True, "no": False}.get(request.POST.get("attended"))
        note = evenings.mark(slot, choice)
        if note:
            messages.success(request, f"Added “Follow up with parents” to {slot.pupil}'s actions.")
    return redirect(f"{reverse('tonight', args=[evening.pk])}#slot-{slot.pk}")


def book_pupil(request, pk):
    """From the class list: this pupil, then a free time at a coming evening. Two taps."""
    pupil = get_object_or_404(Pupil, pk=pk)
    coming = ParentsEvening.objects.filter(date__gte=timezone.localdate()).order_by("date").prefetch_related("slots")
    return render(request, "reports/book.html", {
        "nav": "pupils", "pupil": pupil, "evenings": [
            {"evening": e, "booked": next((s for s in e.slots.all() if s.pupil_id == pupil.pk), None),
             "free": [s for s in e.slots.all() if s.pupil_id is None]}
            for e in coming
        ],
        "back": _local(request, request.GET.get("back")),
    })
