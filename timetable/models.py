import datetime

from django.db import models

from core.models import Base


class Timetable(Base):
    """The school's period structure. The newest one is active; old ones stay for history."""

    name = models.CharField(max_length=100)
    week_cycle = models.PositiveSmallIntegerField(choices=[(1, "One week"), (2, "Two weeks (A/B)")], default=1)
    # [{"label": "P1", "start": "08:50", "end": "09:50"}, ...] in day order
    periods = models.JSONField(default=list)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @classmethod
    def active(cls):
        return cls.objects.order_by("-created_at").first()

    def period(self, label):
        """The period dict for a label, or None if the timetable no longer has it."""
        return next((p for p in self.periods if p["label"] == label), None)

    def period_times(self, label):
        period = self.period(label)
        if period is None:
            return None, None
        return datetime.time.fromisoformat(period["start"]), datetime.time.fromisoformat(period["end"])


class Pupil(Base):
    """First name and surname initial only. No photographs, no full surname, no date of birth."""

    first_name = models.CharField(max_length=40)
    surname_initial = models.CharField(max_length=1)
    year_group = models.PositiveSmallIntegerField(null=True, blank=True)
    instrument = models.CharField(max_length=60, blank=True)
    instrument_teacher = models.CharField(max_length=60, blank=True)
    lessons_in_school = models.BooleanField(default=False)
    remember = models.TextField(blank=True)
    recording_permitted = models.BooleanField(default=False)
    exemplar_reuse_permitted = models.BooleanField(default=False)
    recordings_delete_by = models.DateField(null=True, blank=True)
    upn = models.CharField("UPN", max_length=13, blank=True, help_text="Optional. Used only to match the report export to the school system.")
    left_on = models.DateField(null=True, blank=True, help_text="Set at the rollover for a pupil who has left. Their records stay.")

    class Meta:
        ordering = ["first_name", "surname_initial"]

    def __str__(self):
        return f"{self.first_name} {self.surname_initial}"

    def save(self, *args, **kwargs):
        self.first_name = self.first_name.strip()
        self.surname_initial = self.surname_initial.strip()[:1].upper()
        super().save(*args, **kwargs)


class Class(Base):
    """A timetabled teaching group or a co-curricular one (choir, orchestra); one table for both."""

    TIMETABLED = "timetabled"
    CO_CURRICULAR = "co_curricular"
    KINDS = [(TIMETABLED, "Timetabled"), (CO_CURRICULAR, "Co-curricular")]

    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=20, choices=KINDS, default=TIMETABLED)
    archived_on = models.DateField(null=True, blank=True, help_text="Set at the rollover. An archived class is kept, read-only.")
    year_group = models.PositiveSmallIntegerField(null=True, blank=True)
    pupils = models.ManyToManyField(Pupil, related_name="classes", blank=True)
    term_start = models.DateField(null=True, blank=True)
    term_end = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "classes"

    def __str__(self):
        return self.name


class Slot(Base):
    """The recurring pattern: this class, in this room, in this period, on this day of week A or B."""

    WEEKS = [("A", "Week A"), ("B", "Week B")]
    DAYS = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday")]

    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name="slots")
    week = models.CharField(max_length=1, choices=WEEKS, default="A")
    day = models.PositiveSmallIntegerField(choices=DAYS)
    period = models.CharField(max_length=20)
    room = models.ForeignKey("rooms.Room", on_delete=models.PROTECT, related_name="slots")
    klass = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="slots", verbose_name="class")

    class Meta:
        ordering = ["week", "day", "period"]

    def __str__(self):
        return f"{self.klass} · {self.get_day_display()} {self.period}"


class Session(Base):
    """One actual occurrence. Generated from a slot; the room, period and status are editable per day."""

    PLANNED = "planned"
    TAUGHT = "taught"
    CANCELLED = "cancelled"
    MOVED = "moved"
    STATUSES = [(PLANNED, "Planned"), (TAUGHT, "Taught"), (CANCELLED, "Cancelled"), (MOVED, "Moved")]

    date = models.DateField()
    slot = models.ForeignKey(Slot, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    period = models.CharField(max_length=20)
    room = models.ForeignKey("rooms.Room", on_delete=models.PROTECT, related_name="sessions")
    klass = models.ForeignKey(Class, on_delete=models.PROTECT, related_name="sessions", verbose_name="class")
    lesson = models.ForeignKey("plans.LessonPlan", on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    status = models.CharField(max_length=10, choices=STATUSES, default=PLANNED)

    class Meta:
        ordering = ["date", "period"]
        constraints = [
            models.UniqueConstraint(fields=["date", "slot"], name="one_session_per_slot_per_day"),
        ]

    def __str__(self):
        return f"{self.period} · {self.klass}"


class SessionAttendance(Base):
    """Absence for this session, so the picker skips the pupil. Not a replacement for the school register."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="attendance")
    pupil = models.ForeignKey(Pupil, on_delete=models.CASCADE, related_name="attendance")
    present = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "pupil"], name="one_attendance_per_pupil_per_session")]

    def __str__(self):
        return f"{self.pupil} {'present' if self.present else 'absent'} in {self.session}"


class Rotation(Base):
    """
    The peripatetic grid: pupils leave for instrumental lessons in slots that move week by week.
    `weeks` lists week-commencing Mondays; `slots[w][i]` is [day, period] for slot index i that week.
    """

    name = models.CharField(max_length=60, help_text="E.g. the instrumental teacher and instrument.")
    slot_count = models.PositiveSmallIntegerField()
    weeks = models.JSONField(default=list)
    slots = models.JSONField(default=list)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def when(self, week_monday, slot_index):
        """(day, period) for a slot in a given week, or None if the rotation doesn't run that week."""
        key = week_monday.isoformat()
        if key not in self.weeks or slot_index >= self.slot_count:
            return None
        day, period = self.slots[self.weeks.index(key)][slot_index]
        return day, period


class PupilRotation(Base):
    pupil = models.ForeignKey(Pupil, on_delete=models.CASCADE, related_name="rotations")
    rotation = models.ForeignKey(Rotation, on_delete=models.CASCADE, related_name="pupils")
    slot_index = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["slot_index"]
        constraints = [models.UniqueConstraint(fields=["pupil", "rotation"], name="one_slot_per_pupil_per_rotation")]

    def __str__(self):
        return f"{self.pupil} in {self.rotation}, slot {self.slot_index + 1}"
