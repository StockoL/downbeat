from django import forms

from timetable.forms import DATE
from timetable.models import Pupil

from .models import FlagType, PupilFlag, Relationship


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
