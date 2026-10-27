from django.db import models

from core.models import Base

# The reserved flag palette: eight hues defined in downbeat.css as --flag-1 … --flag-8 and used
# nowhere else in the interface. A flag type picks one by number, never a free colour.
FLAG_COLOURS = [(n, f"Colour {n}") for n in range(1, 9)]


class FlagType(Base):
    """What a flag means lives in the teacher's head; the label is private and shown on the pupil page only."""

    ATTENTION = "attention"
    ADJUSTMENT = "adjustment"
    OTHER = "other"
    CATEGORIES = [(ATTENTION, "Attention"), (ADJUSTMENT, "Adjustment"), (OTHER, "Other")]

    PLACEMENT_RULES = [
        ("none", "No rule"),
        ("front", "Near the front"),
        ("near_teacher", "Near the teacher"),
        ("near_door", "Near the door"),
        ("away_from_window", "Away from the window"),
    ]

    label = models.CharField(max_length=60)
    colour = models.PositiveSmallIntegerField(choices=FLAG_COLOURS, unique=True)
    category = models.CharField(max_length=12, choices=CATEGORIES, default=OTHER)
    placement_rule = models.CharField(max_length=20, choices=PLACEMENT_RULES, default="none")
    what_works = models.TextField(blank=True, help_text="The minimal pupil passport: what helps.")

    class Meta:
        ordering = ["colour"]

    def __str__(self):
        return self.label


class PupilFlag(Base):
    pupil = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="flags")
    flag_type = models.ForeignKey(FlagType, on_delete=models.PROTECT, related_name="pupil_flags")
    since = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["flag_type__colour"]
        constraints = [models.UniqueConstraint(fields=["pupil", "flag_type"], name="one_of_each_flag_per_pupil")]

    def __str__(self):
        return f"{self.pupil}: {self.flag_type}"


class Relationship(Base):
    """Symmetric: stored once per pair, with the two pupils in a fixed order."""

    KEEP_APART = "keep_apart"
    PAIR_WELL = "pair_well"
    KINDS = [(KEEP_APART, "Keep apart"), (PAIR_WELL, "Pair well")]

    pupil_a = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="+")
    pupil_b = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=10, choices=KINDS)
    source = models.CharField(max_length=100, blank=True, help_text="Who told you, e.g. the head of year.")
    since = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pupil_a", "pupil_b"], name="one_relationship_per_pair"),
            models.CheckConstraint(condition=models.Q(pupil_a__lt=models.F("pupil_b")), name="pair_in_fixed_order"),
        ]

    def __str__(self):
        return f"{self.pupil_a} and {self.pupil_b}: {self.get_kind_display().lower()}"

    def save(self, *args, **kwargs):
        if self.pupil_a_id and self.pupil_b_id and str(self.pupil_a_id) > str(self.pupil_b_id):
            self.pupil_a_id, self.pupil_b_id = self.pupil_b_id, self.pupil_a_id
        super().save(*args, **kwargs)

    @classmethod
    def involving(cls, pupil):
        return cls.objects.filter(models.Q(pupil_a=pupil) | models.Q(pupil_b=pupil)).select_related("pupil_a", "pupil_b")

    def other(self, pupil):
        return self.pupil_b if self.pupil_a_id == pupil.pk else self.pupil_a


GROUP_TINTS = [(n, f"Tint {n}") for n in range(1, 7)]


class Group(Base):
    """A working group within a class. Ended, not deleted, so its history stays."""

    klass = models.ForeignKey("timetable.Class", on_delete=models.CASCADE, related_name="groups", verbose_name="class")
    name = models.CharField(max_length=60)
    working_on = models.CharField(max_length=200, blank=True)
    started = models.DateField()
    ended = models.DateField(null=True, blank=True)
    tint = models.PositiveSmallIntegerField(choices=GROUP_TINTS, default=1)

    class Meta:
        ordering = ["ended", "name"]

    def __str__(self):
        return self.name

    @classmethod
    def free_tint(cls, klass):
        """The tint used least by the class's active groups."""
        used = list(cls.objects.filter(klass=klass, ended__isnull=True).values_list("tint", flat=True))
        return min(range(1, 7), key=lambda t: (used.count(t), t))


class GroupMember(Base):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="members")
    pupil = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="group_memberships")
    role = models.CharField(max_length=40, blank=True, help_text="Optional: drums, keys, vocals…")

    class Meta:
        ordering = ["pupil__first_name"]
        constraints = [models.UniqueConstraint(fields=["group", "pupil"], name="one_membership_per_group")]

    def __str__(self):
        return f"{self.pupil} in {self.group}"


class LoanItem(Base):
    """Equipment the department lends."""

    KINDS = [("headphones", "Headphones"), ("ukulele", "Ukulele"), ("cable", "Cable"), ("other", "Other")]

    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=12, choices=KINDS, default="other")
    identifier = models.CharField(max_length=40, blank=True, help_text="A number or label on the item.")
    condition_note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["kind", "identifier", "name"]

    def __str__(self):
        return f"{self.name} {self.identifier}".strip()


class Loan(Base):
    item = models.ForeignKey(LoanItem, on_delete=models.CASCADE, related_name="loans")
    pupil = models.ForeignKey("timetable.Pupil", on_delete=models.CASCADE, related_name="loans")
    out_at = models.DateTimeField()
    due = models.DateField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    condition_on_return = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-out_at"]
        constraints = [
            # An item can only be out to one pupil at a time.
            models.UniqueConstraint(fields=["item"], condition=models.Q(returned_at__isnull=True), name="one_open_loan_per_item"),
        ]

    def __str__(self):
        return f"{self.item} to {self.pupil}"
