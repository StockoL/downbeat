"""
Pupils → class → Missing out: who has had the fewest house points and the fewest turns.
Plain counts, fewest first; no scores and no averages.
"""

import datetime
from collections import Counter

from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from notes.models import Note, SpokenTo
from timetable.models import Class, SessionAttendance

DEFAULT_WEEKS = 7  # about a half term


def window_start(klass, today):
    if klass.term_start and klass.term_start <= today:
        return klass.term_start
    return today - datetime.timedelta(weeks=DEFAULT_WEEKS)


def missing_out(klass, since):
    """[{pupil, house_points, spoken, absences}, ...], fewest house points then fewest turns first."""
    pupils = list(klass.pupils.all())
    lessons = {"session__klass": klass, "session__date__gte": since}
    house_points = Counter(
        Note.objects.live().filter(note_type__is_house_point=True, **lessons).values_list("pupil_id", flat=True)
    )
    spoken = Counter(SpokenTo.objects.filter(**lessons).values_list("pupil_id", flat=True))
    absences = Counter(SessionAttendance.objects.filter(present=False, **lessons).values_list("pupil_id", flat=True))
    rows = [
        {"pupil": p, "house_points": house_points[p.pk], "spoken": spoken[p.pk], "absences": absences[p.pk]}
        for p in pupils
    ]
    rows.sort(key=lambda r: (r["house_points"], r["spoken"], r["pupil"].first_name))
    return rows


def missing_out_page(request, pk):
    klass = get_object_or_404(Class, pk=pk)
    today = timezone.localdate()
    try:
        since = datetime.date.fromisoformat(request.GET["since"])
    except (KeyError, ValueError):
        since = window_start(klass, today)
    return render(request, "pupils/missing_out.html", {
        "nav": "pupils", "klass": klass, "since": since, "rows": missing_out(klass, since),
    })
