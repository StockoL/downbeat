import datetime

from django import forms

from .models import Class, Pupil, Session, Slot, Timetable

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def period_choices(timetable):
    return [(p["label"], f'{p["label"]} ({p["start"]}–{p["end"]})') for p in timetable.periods]


class TimetableEditForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ["name", "week_cycle"]
        widgets = {"week_cycle": forms.RadioSelect}


class PupilForm(forms.ModelForm):
    class Meta:
        model = Pupil
        fields = [
            "first_name", "surname_initial", "year_group", "instrument", "instrument_teacher",
            "lessons_in_school", "remember", "recording_permitted", "exemplar_reuse_permitted",
            "recordings_delete_by",
        ]
        labels = {"lessons_in_school": "Has instrumental lessons in school"}
        help_texts = {"surname_initial": "One letter. Downbeat never stores a full surname."}
        widgets = {
            "remember": forms.Textarea(attrs={"rows": 3}),
            "recordings_delete_by": DATE,
        }

    def clean_surname_initial(self):
        initial = self.cleaned_data["surname_initial"].strip()
        if not initial.isalpha():
            raise forms.ValidationError("Use a single letter.")
        return initial.upper()


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ["name", "kind", "year_group", "term_start", "term_end"]
        widgets = {"kind": forms.RadioSelect, "term_start": DATE, "term_end": DATE}


def parse_pupil_lines(text):
    """
    One pupil per line. The last word is the surname, of which only the initial is kept,
    so a pasted register line ("Aleya Khan") becomes "Aleya K". Lines with one word are skipped.
    """
    pupils, skipped = [], []
    for line in text.splitlines():
        words = line.split()
        if not words:
            continue
        if len(words) < 2 or not words[-1][0].isalpha():
            skipped.append(line.strip())
            continue
        pupils.append((" ".join(words[:-1]), words[-1][0].upper()))
    return pupils, skipped


class AddPupilsForm(forms.Form):
    names = forms.CharField(
        label="New pupils",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Aleya K\nJojo P"}),
        required=False,
        help_text="One per line: first name and surname initial. A full surname is cut to its initial.",
    )
    existing = forms.ModelMultipleChoiceField(
        label="Existing pupils", queryset=Pupil.objects.none(), required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
        help_text="For co-curricular groups that draw on several classes.",
    )

    def __init__(self, *args, klass, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["existing"].queryset = Pupil.objects.exclude(classes=klass)


class SlotForm(forms.ModelForm):
    class Meta:
        model = Slot
        fields = ["week", "day", "period", "klass", "room"]

    def __init__(self, *args, timetable, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.timetable = timetable
        self.fields["period"] = forms.ChoiceField(choices=period_choices(timetable))
        if timetable.week_cycle == 1:
            del self.fields["week"]


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ["date", "period", "klass", "room", "status"]
        widgets = {"date": DATE}

    def __init__(self, *args, timetable, **kwargs):
        super().__init__(*args, **kwargs)
        choices = period_choices(timetable)
        if self.instance.period and self.instance.period not in dict(choices):
            choices.append((self.instance.period, self.instance.period))
        self.fields["period"] = forms.ChoiceField(choices=choices)


class GenerateSessionsForm(forms.Form):
    start = forms.DateField(label="From", widget=DATE)
    end = forms.DateField(label="To", widget=DATE)
    first_week = forms.ChoiceField(
        label="The week of the first date is", choices=Slot.WEEKS, initial="A", widget=forms.RadioSelect,
    )

    def __init__(self, *args, timetable, **kwargs):
        super().__init__(*args, **kwargs)
        if timetable.week_cycle == 1:
            del self.fields["first_week"]

    def clean(self):
        data = super().clean()
        start, end = data.get("start"), data.get("end")
        if start and end:
            if end < start:
                raise forms.ValidationError("The end date is before the start date.")
            if end - start > datetime.timedelta(days=366):
                raise forms.ValidationError("Generate a year or less at a time.")
        return data
