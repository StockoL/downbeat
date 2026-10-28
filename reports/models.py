"""
Summative judgement and reports. A band is the teacher's judgement against exemplars, with the
component evidence in view; nothing here computes one, averages states or suggests a band.
Reports are drafted here and copied out: Downbeat never writes to the school's systems.
"""

from django.db import models
from django.utils import timezone

from core.models import Base


class SummativeJudgement(Base):
    """One band for one strand of one unit, entered by the teacher."""

    pupil = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="judgements")
    unit = models.ForeignKey("plans.Unit", on_delete=models.CASCADE, related_name="judgements")
    strand = models.ForeignKey("assessment.Strand", on_delete=models.PROTECT, related_name="judgements")
    band = models.ForeignKey("assessment.Band", on_delete=models.PROTECT, related_name="judgements")
    evidence_note = models.CharField(max_length=300, blank=True)
    judged_at = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["unit", "strand__order"]
        constraints = [models.UniqueConstraint(fields=["pupil", "unit", "strand"], name="one_judgement_per_strand_per_unit")]

    def __str__(self):
        return f"{self.pupil} · {self.unit} · {self.strand}: {self.band}"
