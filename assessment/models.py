"""
Assessment: teacher-defined strands and bands, the components a unit declares, and what was
seen against them. Nothing here computes a band, averages states or derives a figure.
"""

from django.db import models

from core.models import Base


class Strand(Base):
    """Performing, composing, listening, or whatever the department uses."""

    name = models.CharField(max_length=60)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Band(Base):
    """Teacher-defined vocabulary for summative judgements; nothing assumes how many there are."""

    name = models.CharField(max_length=40)
    order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Component(Base):
    """Something observable a unit sets out to see, in words a pupil would recognise."""

    unit = models.ForeignKey("plans.Unit", on_delete=models.CASCADE, related_name="components")
    order = models.PositiveSmallIntegerField(default=0)
    text = models.CharField(max_length=200, help_text="Pupil-facing and observable: what they can do.")
    strand = models.ForeignKey(Strand, on_delete=models.PROTECT, related_name="components")
    next_step_default = models.CharField(max_length=200, help_text="Attached to an observation unless changed.")
    cumulative_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="built_on_by",
        help_text="An earlier component this one builds on.",
    )

    class Meta:
        ordering = ["unit", "order"]

    def __str__(self):
        return self.text


class FeedbackCode(Base):
    """Numbered codes on a slide: a whole-class way to say what to do next."""

    unit = models.ForeignKey("plans.Unit", on_delete=models.CASCADE, related_name="feedback_codes")
    number = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=200)
    component = models.ForeignKey(Component, on_delete=models.SET_NULL, null=True, blank=True, related_name="feedback_codes")
    action = models.CharField(max_length=200, blank=True, help_text="What the pupil does about it.")

    class Meta:
        ordering = ["unit", "number"]
        constraints = [models.UniqueConstraint(fields=["unit", "number"], name="one_code_per_number_per_unit")]

    def __str__(self):
        return f"{self.number}. {self.text}"


class Observation(Base):
    """
    What was seen against a component. Only kept with a next step or a recording attached, and its
    state may move backwards: nothing here is progress arithmetic.
    """

    NOT_YET = "not_yet"
    PARTLY = "partly"
    SECURE = "secure"
    STATES = [(NOT_YET, "Not yet"), (PARTLY, "Partly"), (SECURE, "Secure")]
    ASSESSORS = [("teacher", "Teacher"), ("self", "Self"), ("peer", "Peer")]

    session = models.ForeignKey("timetable.Session", on_delete=models.PROTECT, related_name="observations")
    pupil = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="observations")
    component = models.ForeignKey(Component, on_delete=models.PROTECT, related_name="observations")
    state = models.CharField(max_length=8, choices=STATES)
    assessor = models.CharField(max_length=8, choices=ASSESSORS, default="teacher")
    next_step = models.CharField(max_length=200, blank=True)
    recording_path = models.CharField(max_length=500, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(next_step="") | ~models.Q(recording_path=""), name="observation_has_next_step_or_recording",
            ),
        ]

    def __str__(self):
        return f"{self.pupil} · {self.component}: {self.get_state_display().lower()}"


class Check(Base):
    """
    A hinge question. Planned on a lesson (the unit's lessons together are the bank), or asked in
    a session: a copy of the planned question with the decision it led to. The decision is the
    record, never the votes, so a session's check exists only once something was decided. Taking
    a decision back blanks it rather than deleting the row, so a late resend can't revive it.
    """

    RE_TAUGHT = "re_taught"
    MOVED_ON = "moved_on"
    PAIRED = "paired"
    DECISIONS = [(RE_TAUGHT, "Re-taught"), (MOVED_ON, "Moved on"), (PAIRED, "Paired")]

    lesson_plan = models.ForeignKey("plans.LessonPlan", on_delete=models.CASCADE, null=True, blank=True, related_name="checks")
    session = models.ForeignKey("timetable.Session", on_delete=models.PROTECT, null=True, blank=True, related_name="checks")
    source = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="asked")
    question = models.TextField()
    answer = models.CharField(max_length=200)
    distractors = models.JSONField(default=list, blank=True, help_text='[{"text": ..., "misconception": ...}]')
    threshold = models.PositiveSmallIntegerField(default=80, help_text="Move on if at least this percentage get it right.")
    decision = models.CharField(max_length=12, choices=DECISIONS, blank=True)
    minutes_in = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(lesson_plan__isnull=False, session__isnull=True)
                | models.Q(lesson_plan__isnull=True, session__isnull=False),
                name="check_is_planned_or_asked",
            ),
            models.UniqueConstraint(fields=["lesson_plan"], condition=models.Q(lesson_plan__isnull=False), name="one_check_per_lesson"),
            models.UniqueConstraint(fields=["session", "source"], condition=models.Q(session__isnull=False), name="one_decision_per_check"),
        ]

    def __str__(self):
        return self.question

    @property
    def options(self):
        """The answer first, then each distractor; a response stores its position in this list."""
        return [{"text": self.answer, "misconception": ""}, *self.distractors]

    def ask_in(self, session, **fields):
        """This planned check's copy for a session, so the record survives later edits to the plan."""
        return Check.objects.create(
            session=session, source=self, question=self.question, answer=self.answer,
            distractors=self.distractors, threshold=self.threshold, **fields,
        )


class CheckResponse(Base):
    """One pupil's answer to a check. Opt-in per unit and entered in the sweep; empty by default."""

    check_asked = models.ForeignKey(Check, on_delete=models.CASCADE, related_name="responses")
    pupil = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="check_responses")
    option = models.PositiveSmallIntegerField(help_text="0 is the answer; 1 onwards the distractors in order.")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["check_asked", "pupil"], name="one_response_per_pupil")]
