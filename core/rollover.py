"""
The rollover, before a new school year: last year's classes archived read-only, pupils carried
forward (or marked as left) with flags and keep-aparts reviewed, open actions closed or carried on
purpose, and recordings past their date removed. Observations, feedback and judgements stay with
each pupil, so their timeline crosses the year. A backup is taken first.
"""

import datetime

from django.db import transaction
from django.db.models import ProtectedError, Q
from django.utils import timezone

from assessment import recordings
from notes.models import Note
from pupils.models import Group, PupilFlag, Relationship
from timetable.models import Class, Pupil, Session, Slot

STALE_AFTER = datetime.timedelta(days=365)


def _stale(since, created, today):
    return (since or created.date()) <= today - STALE_AFTER


def preview(today=None):
    """Everything the rollover will ask about, with the defaults the page starts from."""
    today = today or timezone.localdate()
    classes = list(Class.objects.filter(archived_on__isnull=True).prefetch_related("pupils"))
    pupils = list(Pupil.objects.filter(left_on__isnull=True).order_by("year_group", "first_name", "surname_initial"))
    ids = [p.pk for p in pupils]
    flags = list(PupilFlag.objects.filter(pupil_id__in=ids).select_related("pupil", "flag_type"))
    pairs = list(Relationship.objects.filter(Q(pupil_a_id__in=ids) | Q(pupil_b_id__in=ids)).select_related("pupil_a", "pupil_b"))
    return {
        "classes": classes,
        "pupils": [{"pupil": p, "next_year": p.year_group + 1 if p.year_group else None} for p in pupils],
        "flags": [{"flag": f, "stale": _stale(f.since, f.created_at, today)} for f in flags],
        "relationships": [{"relationship": r, "stale": _stale(r.since, r.created_at, today)} for r in pairs],
        "actions": list(Note.objects.open_actions().filter(session__klass__in=classes)
                        .select_related("pupil", "group", "note_type", "session__klass")),
        "recordings": recordings.paths(recordings.due(today)),
    }


@transaction.atomic
def apply(*, archive, leaving, year_groups, drop_flags, drop_relationships, carry_actions, today=None):
    """
    archive: class ids; leaving: pupil ids; year_groups: {pupil id: new year group or None};
    drop_flags, drop_relationships: ids to remove; carry_actions: open action ids to leave open.
    Returns a summary of what changed.
    """
    today = today or timezone.localdate()
    now = timezone.now()
    classes = list(Class.objects.filter(pk__in=archive, archived_on__isnull=True))
    summary = {"archived": len(classes), "slots": 0, "sessions_removed": 0, "sessions_cancelled": 0}

    for klass in classes:
        summary["slots"] += Slot.objects.filter(klass=klass).delete()[0]  # past sessions keep their date and period
        for session in Session.objects.filter(klass=klass, date__gt=today):
            try:
                with transaction.atomic():
                    session.delete()
                summary["sessions_removed"] += 1
            except ProtectedError:  # something was recorded in it: keep it, cancelled
                Session.objects.filter(pk=session.pk).update(status=Session.CANCELLED)
                summary["sessions_cancelled"] += 1
        Group.objects.filter(klass=klass, ended__isnull=True).update(ended=today)
    Class.objects.filter(pk__in=[c.pk for c in classes]).update(archived_on=today)

    open_actions = Note.objects.open_actions().filter(session__klass__in=classes).exclude(pk__in=carry_actions)
    summary["actions_closed"] = open_actions.update(done_at=now, updated_at=now)

    summary["left"] = Pupil.objects.filter(pk__in=leaving, left_on__isnull=True).update(left_on=today)
    moved = 0
    for pupil in Pupil.objects.filter(pk__in=year_groups, left_on__isnull=True):
        if pupil.year_group != year_groups[pupil.pk]:
            pupil.year_group = year_groups[pupil.pk]
            pupil.save(update_fields=["year_group", "updated_at"])
            moved += 1
    summary["moved_up"] = moved

    summary["flags_dropped"] = PupilFlag.objects.filter(pk__in=drop_flags).delete()[0]
    summary["relationships_dropped"] = Relationship.objects.filter(pk__in=drop_relationships).delete()[0]
    summary["recordings"] = recordings.purge(today)
    return summary
