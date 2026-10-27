from django import forms

from notes.models import NoteType
from rooms.models import Room
from timetable.models import Timetable


class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ["name", "week_cycle"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. 2026–27"}),
            "week_cycle": forms.RadioSelect,
        }


class PeriodForm(forms.Form):
    label = forms.CharField(max_length=20, widget=forms.TextInput(attrs={"placeholder": "e.g. P1"}))
    start = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    end = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["end"] <= data["start"]:
            raise forms.ValidationError("A period has to end after it starts.")
        return data


class BasePeriodFormSet(forms.BaseFormSet):
    def as_periods(self):
        """The JSON shape stored on Timetable.periods, in time order."""
        rows = [f.cleaned_data for f in self.forms if f.has_changed() and f.cleaned_data]
        rows.sort(key=lambda r: r["start"])
        return [{"label": r["label"], "start": r["start"].strftime("%H:%M"), "end": r["end"].strftime("%H:%M")} for r in rows]


PeriodFormSet = forms.formset_factory(
    PeriodForm, formset=BasePeriodFormSet, extra=7, min_num=1, validate_min=True
)


class NoteTypeForm(forms.ModelForm):
    class Meta:
        model = NoteType
        fields = ["label", "icon", "is_house_point", "is_actionable_default"]
        labels = {"is_house_point": "House point", "is_actionable_default": "Needs action"}
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "e.g. House point"}),
            "icon": forms.TextInput(attrs={"size": 4}),
        }


NoteTypeFormSet = forms.modelformset_factory(
    NoteType, form=NoteTypeForm, extra=5, min_num=1, validate_min=True
)


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["name"]
        labels = {"name": "Room name"}
        widgets = {"name": forms.TextInput(attrs={"placeholder": "e.g. M2"})}
