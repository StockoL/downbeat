from django.db import models

from core.models import Base


class NoteType(Base):
    """Teacher-defined; the buttons on the note sheet, in order."""

    label = models.CharField(max_length=40)
    icon = models.CharField(max_length=8, blank=True, help_text="An emoji or short symbol shown as the seat badge.")
    is_house_point = models.BooleanField(default=False)
    is_actionable_default = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "label"]

    def __str__(self):
        return self.label


class NoteQuerySet(models.QuerySet):
    def live(self):
        return self.filter(deleted_at__isnull=True)

    def open_actions(self):
        return self.live().filter(actionable=True, done_at__isnull=True)


class Note(Base):
    """One table, four views: seat badge, pupil inbox, lesson log, actions sheet. No type means free text."""

    session = models.ForeignKey("timetable.Session", on_delete=models.PROTECT, related_name="notes")
    pupil = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, null=True, blank=True, related_name="notes")
    group = models.ForeignKey("pupils.Group", on_delete=models.PROTECT, null=True, blank=True, related_name="notes")
    note_type = models.ForeignKey(NoteType, on_delete=models.PROTECT, null=True, blank=True, related_name="notes")
    text = models.TextField(blank=True)
    actionable = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    carried_to_session = models.ForeignKey(
        "timetable.Session", on_delete=models.SET_NULL, null=True, blank=True, related_name="carried_notes",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = NoteQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.pupil or self.group or 'Class'} · {self.label}"

    @property
    def label(self):
        return self.note_type.label if self.note_type else (self.text or "Note")

    @property
    def icon(self):
        return (self.note_type.icon if self.note_type else "") or "✎"


class SpokenTo(Base):
    """One row per tap or picker draw."""

    session = models.ForeignKey("timetable.Session", on_delete=models.CASCADE, related_name="spoken_to")
    pupil = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="spoken_to")

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "spoken to"

    def __str__(self):
        return f"{self.pupil} in {self.session}"


class Goal(Base):
    """
    "House point in 20 lessons this week": counts lessons that got at least one note of a type.
    Shown as a neutral counter in the room view's bar; edited in Settings.
    """

    WEEK = "week"
    TERM = "term"
    SCOPES = [(WEEK, "Each week"), (TERM, "Since the start date")]

    text = models.CharField(max_length=100)
    scope = models.CharField(max_length=4, choices=SCOPES, default=WEEK)
    target_count = models.PositiveSmallIntegerField()
    counts_note_type = models.ForeignKey(NoteType, on_delete=models.CASCADE, related_name="goals")
    klass = models.ForeignKey(
        "timetable.Class", on_delete=models.CASCADE, null=True, blank=True, related_name="goals",
        verbose_name="class", help_text="Leave blank for every class.",
    )
    week_start = models.DateField(help_text="When the goal starts counting.")

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.text


class ChecklistItem(Base):
    """Starter, homework set, exit task: ticked once per lesson."""

    text = models.CharField(max_length=60)
    klass = models.ForeignKey(
        "timetable.Class", on_delete=models.CASCADE, null=True, blank=True, related_name="checklist_items",
        verbose_name="class", help_text="Leave blank for every class.",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "text"]

    def __str__(self):
        return self.text


class ChecklistTick(Base):
    session = models.ForeignKey("timetable.Session", on_delete=models.CASCADE, related_name="checklist_ticks")
    checklist_item = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE, related_name="ticks")
    ticked_at = models.DateTimeField()

    class Meta:
        ordering = ["ticked_at"]
