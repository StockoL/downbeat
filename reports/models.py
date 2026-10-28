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


class ReportSentence(Base):
    """The comment bank: a sentence for a band in a strand, for one unit or any. {name} becomes the pupil's first name."""

    band = models.ForeignKey("assessment.Band", on_delete=models.CASCADE, related_name="sentences")
    strand = models.ForeignKey("assessment.Strand", on_delete=models.CASCADE, related_name="sentences")
    unit = models.ForeignKey("plans.Unit", on_delete=models.CASCADE, null=True, blank=True, related_name="sentences",
                             help_text="Leave blank to use it for any unit.")
    text = models.TextField(help_text="Third person; {name} becomes the pupil's first name.")

    class Meta:
        ordering = ["strand__order", "band__order"]

    def __str__(self):
        return self.text[:60]


class ReportDraft(Base):
    """A pupil's report comment for one class, as edited. Copied out; never sent anywhere."""

    pupil = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="report_drafts")
    klass = models.ForeignKey("timetable.Class", on_delete=models.CASCADE, related_name="report_drafts")
    text = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["pupil", "klass"], name="one_draft_per_pupil_per_class")]


class ReportStyle(Base):
    """The school's house style, set by the teacher: one row, made the first time it is saved."""

    length_cap = models.PositiveSmallIntegerField(null=True, blank=True, help_text="The school system's character limit, if it has one.")
    third_person = models.BooleanField(default=True, help_text="Warn when a comment says \"you\", \"your\", \"I\" or \"my\".")

    @classmethod
    def current(cls):
        return cls.objects.first() or cls()
