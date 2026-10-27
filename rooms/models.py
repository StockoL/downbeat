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


class SeatingPlan(Base):
    """One class's arrangement in one room. A class may have plans in several rooms."""

    klass = models.ForeignKey("timetable.Class", on_delete=models.CASCADE, related_name="seating_plans", verbose_name="class")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="seating_plans")
    name = models.CharField(max_length=60, blank=True)
    active_from = models.DateField()
    active_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-active_from", "-created_at"]

    def __str__(self):
        return self.name or f"{self.klass} in {self.room}"

    @classmethod
    def current(cls, klass, room, date):
        """The plan in force for this class in this room on this date, or None."""
        return (
            cls.objects.filter(klass=klass, room=room, active_from__lte=date)
            .filter(models.Q(active_to__isnull=True) | models.Q(active_to__gte=date))
            .first()
        )


class SeatAssignment(Base):
    seating_plan = models.ForeignKey(SeatingPlan, on_delete=models.CASCADE, related_name="assignments")
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, related_name="assignments")
    pupil = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="seat_assignments")
    locked = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["seating_plan", "seat"], name="one_pupil_per_seat"),
            models.UniqueConstraint(fields=["seating_plan", "pupil"], name="one_seat_per_pupil"),
        ]

    def __str__(self):
        return f"{self.pupil} at {self.seat}"
