from django.db import models

from core.models import Base

# Seat size in canvas units. The canvas scales to fit, so these are proportions, not pixels.
SEAT_WIDTH = 80
SEAT_HEIGHT = 44


class Room(Base):
    """Drawn once and shared by every class taught in it. Seats are free-placed, not a grid."""

    name = models.CharField(max_length=100)
    canvas_width = models.PositiveIntegerField(default=900)
    canvas_height = models.PositiveIntegerField(default=600)
    teacher_x = models.PositiveIntegerField(null=True, blank=True)
    teacher_y = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Seat(Base):
    ZONES = [
        ("front", "Front"),
        ("back", "Back"),
        ("side", "Side"),
        ("carpet", "Carpet"),
        ("keyboard", "Keyboard"),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="seats")
    x = models.PositiveIntegerField(default=0)
    y = models.PositiveIntegerField(default=0)
    label = models.CharField(max_length=20, blank=True)
    zone = models.CharField(max_length=10, choices=ZONES, blank=True)
    near_teacher = models.BooleanField(default=False)

    class Meta:
        ordering = ["y", "x"]

    def __str__(self):
        return self.label or f"Seat at {self.x}, {self.y}"

    def as_dict(self):
        return {
            "id": str(self.id), "x": self.x, "y": self.y, "label": self.label,
            "zone": self.zone, "near_teacher": self.near_teacher,
        }
