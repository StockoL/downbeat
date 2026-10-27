from django import forms

from timetable.forms import DATE
from timetable.models import Pupil

from .models import FlagType, Group, GroupMember, PupilFlag, Relationship


class FlagTypeForm(forms.ModelForm):
    class Meta:
        model = FlagType
        fields = ["colour", "label", "category", "placement_rule", "what_works"]
        labels = {"label": "Private label", "placement_rule": "Seating rule"}
        widgets = {"what_works": forms.Textarea(attrs={"rows": 2})}


FlagTypeFormSet = forms.modelformset_factory(FlagType, form=FlagTypeForm, extra=1, can_delete=True)


class PupilFlagForm(forms.ModelForm):
    class Meta:
        model = PupilFlag
        fields = ["flag_type", "since", "note"]
        labels = {"flag_type": "Flag"}
        widgets = {"since": DATE, "note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, pupil, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.pupil = pupil
        self.fields["flag_type"].queryset = FlagType.objects.exclude(pupil_flags__pupil=pupil)


class RelationshipForm(forms.ModelForm):
    other = forms.ModelChoiceField(label="With", queryset=None)

    class Meta:
        model = Relationship
        fields = ["other", "kind", "source", "since", "note"]
        widgets = {"since": DATE, "note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, pupil, **kwargs):
        super().__init__(*args, **kwargs)
        self.pupil = pupil
        taken = {r.other(pupil).pk for r in Relationship.involving(pupil)}
        self.fields["other"].queryset = (
            Pupil.objects.filter(classes__in=pupil.classes.all()).exclude(pk=pupil.pk).exclude(pk__in=taken).distinct()
        )

    def save(self, commit=True):
        self.instance.pupil_a = self.pupil
        self.instance.pupil_b = self.cleaned_data["other"]
        return super().save(commit)


def free_pupils(klass):
    """The class's pupils not already in one of its active groups."""
    busy = GroupMember.objects.filter(group__klass=klass, group__ended__isnull=True).values("pupil")
    return klass.pupils.exclude(pk__in=busy)


class GroupForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=None, widget=forms.CheckboxSelectMultiple, required=False,
        help_text="Pupils not already in an active group.",
    )

    class Meta:
        model = Group
        fields = ["name", "working_on", "started"]
        labels = {"working_on": "Working on"}
        widgets = {"started": DATE}

    def __init__(self, *args, klass, **kwargs):
        super().__init__(*args, **kwargs)
        self.klass = klass
        self.fields["members"].queryset = free_pupils(klass)

    def save(self, commit=True):
        self.instance.klass = self.klass
        self.instance.tint = Group.free_tint(self.klass)
        group = super().save(commit)
        GroupMember.objects.bulk_create([GroupMember(group=group, pupil=p) for p in self.cleaned_data["members"]])
        return group


class MemberForm(forms.ModelForm):
    class Meta:
        model = GroupMember
        fields = ["pupil", "role"]

    def __init__(self, *args, group, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.group = group
        self.fields["pupil"].queryset = free_pupils(group.klass)
