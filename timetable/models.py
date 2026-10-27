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
