"""
The sweep (desk, same day, two minutes): reconcile the lesson that happened with the one planned.
Activity statuses, caught notes kept or binned, one reflection line, and unfinished activities
carried to the class's next session, where they show as carry-forward prompts.
"""

from django.db import transaction
from django.utils import timezone

from notes.models import Note
from timetable.models import Session, Timetable
from timetable.services import period_order

from .models import ActivityStatus, PlanActivity, SessionReflection


def next_for_class(session):
    """The class's next session after this one that isn't cancelled, or None."""
    order = period_order(Timetable.active())

    def rank(s):
        return (s.date, order.get(s.period, len(order)), s.period)

    later = Session.objects.filter(klass_id=session.klass_id, date__gte=session.date).exclude(status=Session.CANCELLED).exclude(pk=session.pk)
    candidates = sorted((s for s in later if rank(s) > rank(session)), key=rank)
    return candidates[0] if candidates else None


def is_swept(session):
    return SessionReflection.objects.filter(session=session).exists()


@transaction.atomic
def save_sweep(session, statuses, carry, binned, text, tags):
    """
    statuses: {activity_id: status}; carry: activity ids to carry forward; binned: note ids to remove.
    Marks the session taught and swept. Returns the session the carried activities went to, if any.
    """
    activities = {str(a.pk): a for a in PlanActivity.objects.filter(lesson_plan=session.lesson)} if session.lesson else {}
    target = next_for_class(session)
    for activity_id, status in statuses.items():
        activity = activities.get(str(activity_id))
        if activity is None or status not in dict(ActivityStatus.STATUSES):
            continue
        unfinished = status != ActivityStatus.DONE
        ActivityStatus.objects.update_or_create(
            session=session, plan_activity=activity,
            defaults={
                "status": status,
                "carried_to_session": target if unfinished and str(activity_id) in carry else None,
            },
        )
    Note.objects.filter(session=session, pk__in=binned, deleted_at__isnull=True).update(
        deleted_at=timezone.now(), updated_at=timezone.now(),
    )
    SessionReflection.objects.update_or_create(session=session, defaults={"text": text.strip(), "tags": tags})
    if session.status == Session.PLANNED:
        session.status = Session.TAUGHT
        session.save(update_fields=["status", "updated_at"])
    return target


@transaction.atomic
def give_to_members(note):
    """A group note, attributed explicitly to each member: one copy per pupil. Returns how many."""
    members = [m.pupil for m in note.group.members.select_related("pupil")]
    already = set(
        Note.objects.filter(session=note.session, note_type=note.note_type, text=note.text, pupil__in=members)
        .values_list("pupil_id", flat=True)
    )
    made = [
        Note(session=note.session, pupil=pupil, note_type=note.note_type, text=note.text, actionable=note.actionable)
        for pupil in members if pupil.pk not in already
    ]
    Note.objects.bulk_create(made)
    return len(made)


def carried_into(session):
    """Activities carried to this session from earlier ones: the carry-forward prompts."""
    return (
        ActivityStatus.objects.filter(carried_to_session=session)
        .select_related("plan_activity", "session")
        .order_by("session__date", "plan_activity__order")
    )
