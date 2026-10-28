"""Settings → Rollover: the review page for a new school year, and bringing a class back from the archive."""

import uuid

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from timetable.models import Class

from . import data, rollover


def _ids(values, allowed):
    """Only the ids the page offered, as UUIDs; anything else is ignored."""
    chosen = set()
    for value in values:
        try:
            chosen.add(uuid.UUID(value))
        except ValueError:
            continue
    return chosen & set(allowed)


def rollover_page(request):
    found = rollover.preview()
    if request.method != "POST":
        return render(request, "core/rollover.html", {"nav": "settings", "section": "rollover", **found})

    try:
        backup = data.backup()
    except data.BackupFailed as error:
        messages.error(request, f"The rollover needs a backup first, and that failed: {error}")
        return redirect("rollover")
    pupils = [row["pupil"].pk for row in found["pupils"]]
    leaving = _ids(request.POST.getlist("leaving"), pupils)
    year_groups = {}
    for pk in pupils:
        value = request.POST.get(f"year-{pk}", "").strip()
        if pk not in leaving:
            year_groups[pk] = int(value) if value.isdigit() and 1 <= int(value) <= 14 else None
    flags = [row["flag"].pk for row in found["flags"]]
    pairs = [row["relationship"].pk for row in found["relationships"]]
    summary = rollover.apply(
        archive=_ids(request.POST.getlist("archive"), [c.pk for c in found["classes"]]),
        leaving=leaving, year_groups=year_groups,
        drop_flags=set(flags) - _ids(request.POST.getlist("keep_flag"), flags),
        drop_relationships=set(pairs) - _ids(request.POST.getlist("keep_relationship"), pairs),
        carry_actions=_ids(request.POST.getlist("carry"), [n.pk for n in found["actions"]]),
    )
    messages.success(request, (
        f"Rolled over, after a backup to {backup.name}. Archived {summary['archived']} classes; "
        f"{summary['moved_up']} pupils moved up and {summary['left']} marked as left; "
        f"{summary['flags_dropped']} flags and {summary['relationships_dropped']} seating notes dropped; "
        f"{summary['actions_closed']} actions closed."
    ))
    if summary["recordings"]:
        messages.warning(request, "Recording references removed; delete these files too: " + "; ".join(summary["recordings"]))
    return redirect("rollover")


@require_POST
def class_unarchive(request, pk):
    klass = get_object_or_404(Class, pk=pk, archived_on__isnull=False)
    klass.archived_on = None
    klass.save(update_fields=["archived_on", "updated_at"])
    messages.success(request, f"{klass} is back from the archive. Its weekly slots were removed at the rollover; add them again if it is taught.")
    return redirect("class_detail", pk=klass.pk)
