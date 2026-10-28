"""Sweep (desk, same day): today's sessions, and each session's two-minute sweep."""

import datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from assessment import hinge
from notes.models import Goal, Note, NoteType
from timetable.models import Session, Timetable
from timetable.services import sessions_on

from . import sweep
from .models import REFLECTION_TAGS, ActivityStatus, SessionReflection


def sweep_home(request):
    """A day's sessions as cards with a tick once swept; the first unswept one is highlighted."""
    try:
        day = datetime.date.fromisoformat(request.GET["date"])
    except (KeyError, ValueError):
        day = timezone.localdate()
    sessions = [s for s in sessions_on(day, Timetable.active()) if s.status != Session.CANCELLED]
    swept = set(SessionReflection.objects.filter(session__in=sessions).values_list("session_id", flat=True))
    for session in sessions:
        session.swept = session.pk in swept
    first = next((s for s in sessions if not s.swept), None)
    return render(request, "sweep/home.html", {
        "nav": "sweep", "tab": "sweep", "day": day, "sessions": sessions, "first": first,
        "yesterday": day - datetime.timedelta(days=1), "tomorrow": day + datetime.timedelta(days=1),
    })


def session_sweep(request, pk):
    session = get_object_or_404(Session.objects.select_related("klass", "lesson__unit"), pk=pk)
    if request.method == "POST":
        activity_ids = [str(a.pk) for a in session.lesson.activities.all()] if session.lesson else []
        statuses = {a: request.POST[f"status-{a}"] for a in activity_ids if request.POST.get(f"status-{a}")}
        tags = [t for t in request.POST.getlist("tags") if t in dict(REFLECTION_TAGS)]
        target = sweep.save_sweep(
            session, statuses, set(request.POST.getlist("carry")), request.POST.getlist("bin"),
            request.POST.get("text", ""), tags,
        )
        session.observations.filter(pk__in=request.POST.getlist("bin_observation"), deleted_at__isnull=True).update(
            deleted_at=timezone.now(), updated_at=timezone.now(),
        )
        _, dropped = hinge.judge(session, request.POST.get("hinge_decision", ""), _responses(request, session))
        if dropped:
            messages.error(request, "Pupils' answers are kept only with a decision, so they weren't saved.")
        goal = _spawn_goal(request, session)
        if goal:
            messages.success(request, f"New goal: {goal}. It shows in the room's bar from today.")
        carried = session.activity_statuses.filter(carried_to_session__isnull=False).count()
        if carried and target:
            messages.success(request, f"Swept. {carried} activit{'y' if carried == 1 else 'ies'} carried to {target.date:%a %d %b}.")
        else:
            messages.success(request, "Swept.")
        return redirect(f"{_home(session)}")

    statuses = {s.plan_activity_id: s for s in session.activity_statuses.all()}
    activities = []
    for activity in session.lesson.activities.all() if session.lesson else []:
        status = statuses.get(activity.pk)
        activities.append({"activity": activity, "status": status.status if status else "", "carried": bool(status and status.carried_to_session_id)})
    reflection = SessionReflection.objects.filter(session=session).first()
    return render(request, "sweep/session.html", {
        **_hinge_context(session),
        "nav": "sweep",
        "session": session,
        "activities": activities,
        "statuses": ActivityStatus.STATUSES,
        "notes": session.notes.live().select_related("pupil", "group", "note_type"),
        "observations": session.observations.filter(deleted_at__isnull=True).select_related("pupil", "component"),
        "next": sweep.next_for_class(session),
        "carried_in": sweep.carried_into(session),
        "reflection": reflection,
        "tags": REFLECTION_TAGS,
        "chosen_tags": reflection.tags if reflection else [],
        "note_types": NoteType.objects.all(),
    })


def _responses(request, session):
    """Each pupil's answer from the sweep, only when the unit opts in: {pupil id: option index or None}."""
    if not (session.lesson_id and session.lesson.unit.check_responses):
        return None
    answers = {}
    for pk in session.klass.pupils.values_list("pk", flat=True):
        value = request.POST.get(f"response-{pk}", "")
        answers[str(pk)] = int(value) if value.isdigit() else None
    return answers


def _hinge_context(session):
    asked, planned = hinge.asked_in(session), hinge.planned_for(session)
    check = asked or planned
    if check is None:
        return {}
    context = {"check": check, "asked": asked, "decisions": check.DECISIONS}
    if session.lesson_id and session.lesson.unit.check_responses:
        given = dict(asked.responses.values_list("pupil_id", "option")) if asked else {}
        context["options"] = list(enumerate(check.options))
        context["responses"] = [{"pupil": p, "option": given.get(p.pk)} for p in session.klass.pupils.all()]
    return context


def _spawn_goal(request, session):
    """The reflection's optional "turn this into a goal": a weekly goal, linked to the reflection."""
    text = request.POST.get("goal_text", "").strip()[:100]
    if not text:
        return None
    try:
        note_type = NoteType.objects.filter(pk=request.POST.get("goal_note_type") or None).first()
    except ValidationError:
        note_type = None
    try:
        target = max(1, min(int(request.POST.get("goal_target", "")), 500))
    except ValueError:
        target = None
    if note_type is None or target is None:
        messages.error(request, "The goal needs a note type and a target, so it wasn't made.")
        return None
    goal = Goal.objects.create(
        text=text, counts_note_type=note_type, target_count=target, scope=Goal.WEEK,
        klass=session.klass if request.POST.get("goal_this_class") else None, week_start=timezone.localdate(),
    )
    SessionReflection.objects.filter(session=session).update(spawned_goal=goal)
    return goal


def _home(session):
    from django.urls import reverse

    return f"{reverse('sweep_home')}?date={session.date.isoformat()}"


@require_POST
def give_to_members(request, pk):
    note = get_object_or_404(Note.objects.select_related("group", "session"), pk=pk, group__isnull=False)
    made = sweep.give_to_members(note)
    messages.success(request, f"Given to {made} member{'s' if made != 1 else ''}.")
    return redirect("session_sweep", pk=note.session_id)
