"""Goal tallies and the per-lesson checklist, as the room view's bar shows them."""

import datetime

from django.db.models import Q

from timetable.models import Session

from .models import ChecklistItem, Goal, Note

BAR_GOALS = 2  # the bar has room for two goal counters


def goals_for(session):
    """Goals that apply to this lesson: for its class or every class, already started."""
    return list(
        Goal.objects.filter(Q(klass__isnull=True) | Q(klass=session.klass), week_start__lte=session.date)
        .select_related("counts_note_type")[:BAR_GOALS]
    )


def window(goal, date):
    """The dates a goal counts over, as of `date`."""
    if goal.scope == Goal.WEEK:
        monday = date - datetime.timedelta(days=date.weekday())
        return max(monday, goal.week_start), monday + datetime.timedelta(days=6)
    return goal.week_start, date


def tally(goal, date, exclude=None):
    """Lessons in the goal's window that got at least one live note of its type."""
    start, end = window(goal, date)
    lessons = Session.objects.filter(date__range=(start, end)).exclude(status=Session.CANCELLED)
    if goal.klass_id:
        lessons = lessons.filter(klass_id=goal.klass_id)
    if exclude is not None:
        lessons = lessons.exclude(pk=exclude.pk)
    counted = Note.objects.live().filter(session__in=lessons, note_type_id=goal.counts_note_type_id)
    return counted.values("session").distinct().count()


def checklist_items(session):
    return list(ChecklistItem.objects.filter(Q(klass__isnull=True) | Q(klass=session.klass)))
