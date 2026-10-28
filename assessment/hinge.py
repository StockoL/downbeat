"""The hinge judgement as the sweep records it: the decision from memory, and pupils' answers if the unit opts in."""

from .models import Check, CheckResponse


def planned_for(session):
    return session.lesson.checks.first() if session.lesson_id else None


def asked_in(session):
    return session.checks.order_by("created_at").first()


def judge(session, decision, responses=None):
    """
    Records the class-level decision, asking the planned check in this session if the room didn't.
    A blank decision takes it back. responses ({pupil id: option index or None}) are kept only with
    a decision, since the decision is the record. Returns (the session's check or None, whether
    responses were dropped for want of a decision).
    """
    decision = decision if decision in dict(Check.DECISIONS) else ""
    asked = asked_in(session)
    if asked is None:
        planned = planned_for(session)
        if planned is not None and decision:
            asked = planned.ask_in(session, decision=decision)  # judged afterwards: no minutes in
    elif asked.decision != decision:
        asked.decision = decision
        asked.save(update_fields=["decision", "updated_at"])

    given = {pupil: option for pupil, option in (responses or {}).items() if option is not None}
    if asked is None or not asked.decision:
        return asked, bool(given)
    pupils = {str(pk) for pk in session.klass.pupils.values_list("pk", flat=True)}
    choices = range(len(asked.options))
    for pupil, option in (responses or {}).items():
        if pupil not in pupils:
            continue
        if option is None or option not in choices:
            CheckResponse.objects.filter(check_asked=asked, pupil_id=pupil).delete()
        else:
            CheckResponse.objects.update_or_create(check_asked=asked, pupil_id=pupil, defaults={"option": option})
    return asked, False
