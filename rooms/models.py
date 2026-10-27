from django.db import models

from core.models import Base


class Room(Base):
    """Drawn once and shared by every class taught in it."""

    name = models.CharField(max_length=100)
    canvas_width = models.PositiveIntegerField(default=1000)
    canvas_height = models.PositiveIntegerField(default=700)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
