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
        return f"{self.pupil or 'Class'} · {self.label}"

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
