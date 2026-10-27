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
