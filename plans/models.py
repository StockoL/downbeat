from django.db import models

from core.models import Base


class Scheme(Base):
    """A year group's scheme of work: a skeleton, filled as it is taught."""

    year_group = models.PositiveSmallIntegerField(null=True, blank=True)
    name = models.CharField(max_length=100)
    strand_framework = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["year_group", "name"]

    def __str__(self):
        return self.name


class Unit(Base):
    scheme = models.ForeignKey(Scheme, on_delete=models.CASCADE, related_name="units")
    name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)
    lessons_planned = models.PositiveSmallIntegerField(default=6)
    assessment_notes = models.TextField(blank=True)
    purpose = models.TextField(blank=True, help_text="Why assess this, and what happens to the results?")

    class Meta:
        ordering = ["scheme", "order", "name"]

    def __str__(self):
        return self.name


class LessonPlan(Base):
    """The template a session points at."""

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="lessons")
    order = models.PositiveSmallIntegerField(default=1)
    objective = models.CharField(max_length=200)
    starter = models.TextField(blank=True)
    main = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    differentiation = models.TextField(blank=True)
    homework = models.TextField(blank=True)

    class Meta:
        ordering = ["unit", "order"]

    def __str__(self):
        return f"{self.unit} L{self.order}"


class PlanActivity(Base):
    """The ordered list that makes carry-forward possible."""

    lesson_plan = models.ForeignKey(LessonPlan, on_delete=models.CASCADE, related_name="activities")
    order = models.PositiveSmallIntegerField(default=0)
    text = models.CharField(max_length=200)
    minutes = models.PositiveSmallIntegerField(default=10)

    class Meta:
        ordering = ["lesson_plan", "order"]

    def __str__(self):
        return self.text


class Resource(Base):
    """Referenced, never uploaded: a path or link to where the file lives."""

    lesson_plan = models.ForeignKey(LessonPlan, on_delete=models.CASCADE, related_name="resources")
    title = models.CharField(max_length=100)
    path_or_url = models.CharField(max_length=500, blank=True)
    needs_print = models.BooleanField(default=False)
    copies = models.PositiveSmallIntegerField(default=0)
    setup_note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class ActivityStatus(Base):
    """Set in the sweep. An unfinished activity can be carried to the class's next session."""

    DONE = "done"
    PARTIAL = "partial"
    NOT_REACHED = "not_reached"
    STATUSES = [(DONE, "Done"), (PARTIAL, "Partly"), (NOT_REACHED, "Not reached")]

    session = models.ForeignKey("timetable.Session", on_delete=models.CASCADE, related_name="activity_statuses")
    plan_activity = models.ForeignKey(PlanActivity, on_delete=models.CASCADE, related_name="statuses")
    status = models.CharField(max_length=12, choices=STATUSES)
    carried_to_session = models.ForeignKey(
        "timetable.Session", on_delete=models.SET_NULL, null=True, blank=True, related_name="carried_activities",
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "plan_activity"], name="one_status_per_activity_per_session")]


# Tags for a reflection: the Teachers' Standards, short.
REFLECTION_TAGS = [
    ("TS1", "High expectations"),
    ("TS2", "Progress"),
    ("TS3", "Subject knowledge"),
    ("TS4", "Planning"),
    ("TS5", "Adaptive teaching"),
    ("TS6", "Assessment"),
    ("TS7", "Behaviour"),
    ("TS8", "Wider responsibilities"),
]


class SessionReflection(Base):
    """One or two lines from the sweep. Its existence marks the session as swept."""

    session = models.OneToOneField("timetable.Session", on_delete=models.CASCADE, related_name="reflection")
    text = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    spawned_goal = models.ForeignKey("notes.Goal", on_delete=models.SET_NULL, null=True, blank=True, related_name="spawned_from")

    def __str__(self):
        return self.text[:60] or "Swept"
