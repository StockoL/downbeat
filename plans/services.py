from django.db import transaction
from django.utils import timezone

from timetable.models import Session

from .models import LessonPlan, PlanActivity, Resource, Unit


@transaction.atomic
def duplicate_unit(unit, scheme=None):
    """A copy of a unit with its lessons, activities and resources, as the start of next year's version."""
    copy = Unit.objects.create(
        scheme=scheme or unit.scheme, name=f"{unit.name} (copy)", order=unit.order + 1,
        lessons_planned=unit.lessons_planned, assessment_notes=unit.assessment_notes, purpose=unit.purpose,
    )
    for lesson in unit.lessons.prefetch_related("activities", "resources"):
        new = LessonPlan.objects.create(
            unit=copy, order=lesson.order, objective=lesson.objective, starter=lesson.starter, main=lesson.main,
            assessment=lesson.assessment, differentiation=lesson.differentiation, homework=lesson.homework,
        )
        PlanActivity.objects.bulk_create([
            PlanActivity(lesson_plan=new, order=a.order, text=a.text, minutes=a.minutes) for a in lesson.activities.all()
        ])
        Resource.objects.bulk_create([
            Resource(lesson_plan=new, title=r.title, path_or_url=r.path_or_url, needs_print=r.needs_print,
                     copies=r.copies, setup_note=r.setup_note)
            for r in lesson.resources.all()
        ])
    return copy


def upcoming_sessions(klass, from_date=None):
    return Session.objects.filter(klass=klass, date__gte=from_date or timezone.localdate()).exclude(
        status=Session.CANCELLED
    ).order_by("date", "period")


@transaction.atomic
def fill_from_unit(klass, unit, from_date=None):
    """
    Give the class's upcoming sessions without a lesson the unit's lessons in order, carrying on
    after the last of the unit's lessons the class already has. Returns how many were filled.
    """
    already = Session.objects.filter(klass=klass, lesson__unit=unit).exclude(status=Session.CANCELLED)
    last = max((s.lesson.order for s in already.select_related("lesson")), default=0)
    lessons = list(unit.lessons.filter(order__gt=last))
    filled = 0
    for session, lesson in zip(upcoming_sessions(klass, from_date).filter(lesson__isnull=True), lessons, strict=False):
        session.lesson = lesson
        session.save(update_fields=["lesson", "updated_at"])
        filled += 1
    return filled
