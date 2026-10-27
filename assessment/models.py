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
