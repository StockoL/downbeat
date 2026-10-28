from django import forms

from .models import Check, Component, Feedback

DISTRACTORS = 4


class HingeForm(forms.Form):
    """A lesson's hinge check, edited with the lesson. Blank question, no check."""

    question = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Asked at the lesson's hinge point. Leave blank for no check.",
    )
    answer = forms.CharField(required=False, max_length=200, label="Right answer")
    threshold = forms.IntegerField(required=False, min_value=1, max_value=100, initial=80, label="Move on at (% right)")

    def __init__(self, *args, check=None, **kwargs):
        super().__init__(*args, **kwargs)
        for i in range(1, DISTRACTORS + 1):
            self.fields[f"distractor_{i}"] = forms.CharField(required=False, max_length=200, label=f"Wrong answer {i}")
            self.fields[f"misconception_{i}"] = forms.CharField(required=False, max_length=200, label="The misconception it shows")
        if check is not None and not self.is_bound:
            self.initial.update(question=check.question, answer=check.answer, threshold=check.threshold)
            for i, distractor in enumerate(check.distractors[:DISTRACTORS], start=1):
                self.initial[f"distractor_{i}"] = distractor.get("text", "")
                self.initial[f"misconception_{i}"] = distractor.get("misconception", "")

    def pairs(self):
        """The distractor and misconception fields side by side, for the template."""
        return [(self[f"distractor_{i}"], self[f"misconception_{i}"]) for i in range(1, DISTRACTORS + 1)]

    def clean(self):
        data = super().clean()
        if not data.get("question", "").strip():
            return data
        if not data.get("answer", "").strip():
            self.add_error("answer", "A check needs its right answer.")
        distractors = []
        for i in range(1, DISTRACTORS + 1):
            text = data.get(f"distractor_{i}", "").strip()
            misconception = data.get(f"misconception_{i}", "").strip()
            if text and not misconception:
                self.add_error(f"misconception_{i}", "Say which misconception this wrong answer would show.")
            elif misconception and not text:
                self.add_error(f"distractor_{i}", "A misconception needs the wrong answer that shows it.")
            elif text:
                distractors.append({"text": text, "misconception": misconception})
        if not distractors and not self.errors:
            raise forms.ValidationError("A hinge check needs at least one wrong answer, tagged with its misconception.")
        data["distractors"] = distractors
        data["threshold"] = data.get("threshold") or 80
        return data

    def save(self, lesson):
        """Creates, updates or (when the question is blank) removes the lesson's planned check."""
        question = self.cleaned_data["question"].strip()
        if not question:
            Check.objects.filter(lesson_plan=lesson).delete()
            return None
        check, _ = Check.objects.update_or_create(lesson_plan=lesson, defaults={
            "question": question, "answer": self.cleaned_data["answer"].strip(),
            "distractors": self.cleaned_data["distractors"], "threshold": self.cleaned_data["threshold"],
        })
        return check


def parse_at(text):
    """'1:42' or '102' as seconds; None for blank. Raises ValueError for anything else."""
    text = text.strip()
    if not text:
        return None
    minutes, _, seconds = text.rpartition(":")
    if not seconds.isdigit() or (minutes and not minutes.isdigit()) or (minutes and int(seconds) > 59):
        raise ValueError(text)
    return int(minutes or 0) * 60 + int(seconds)


class LessonChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, session):
        return f"{session.date:%a} {session.date.day} {session.date:%b} {session.period} · {session.klass}" + (
            f" · {session.lesson}" if session.lesson_id else "")


class FeedbackForm(forms.Form):
    """
    Feedback for one pupil or one group, written whenever. From a lesson's page it asks who it's
    for; from a pupil's page it asks which of their lessons it belongs to. A recording only for
    pupils whose families agreed.
    """

    who = forms.ChoiceField(label="For")
    component = forms.ModelChoiceField(queryset=None, required=False, label="Component (optional)")
    done_well = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Done well")
    develop = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="To develop")
    how = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="How")
    recording_path = forms.CharField(required=False, max_length=500, label="Recording",
                                     help_text="A path or link to the recording. Downbeat never uploads it.")
    recording_at = forms.CharField(required=False, max_length=8, label="At (m:ss)",
                                   help_text="The moment the feedback is about, e.g. 1:42 for bar 9.")

    def __init__(self, *args, session=None, pupil=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.session, self.pupil = session, pupil
        if pupil is not None:
            self._for_pupil(pupil)
            return
        from pupils.services import active_groups

        self.pupils = {str(p.pk): p for p in session.klass.pupils.all()}
        self.groups = {str(g.pk): g for g in active_groups(session.klass)}
        choices = [("", "Choose…"), ("Pupils", [(f"pupil:{pk}", str(p)) for pk, p in self.pupils.items()])]
        if self.groups:
            choices.append(("Groups", [(f"group:{pk}", str(g)) for pk, g in self.groups.items()]))
        self.fields["who"].choices = choices
        self.fields["component"].queryset = session.lesson.unit.components.all() if session.lesson_id else Component.objects.none()

    def _for_pupil(self, pupil):
        """The pupil's lessons, newest first, the latest chosen; components from those lessons' units."""
        from django.utils import timezone

        from timetable.models import Session

        lessons = (Session.objects.filter(klass__pupils=pupil, date__lte=timezone.localdate())
                   .exclude(status=Session.CANCELLED).select_related("klass", "lesson").order_by("-date", "-period"))
        del self.fields["who"]
        self.fields = {"lesson": LessonChoiceField(queryset=lessons, label="Lesson", empty_label=None), **self.fields}
        self.fields["lesson"].initial = lessons.first()
        self.fields["component"].queryset = Component.objects.filter(unit__lessons__sessions__in=lessons).distinct()

    def clean(self):
        data = super().clean()
        if self.pupil is not None:
            data["pupil"], data["group"] = self.pupil, None
            lesson = data.get("lesson")
            if lesson is None:
                raise forms.ValidationError("Choose the lesson this feedback belongs to.")
            self.session = lesson
            component = data.get("component")
            if component and (not lesson.lesson_id or component.unit_id != lesson.lesson.unit_id):
                self.add_error("component", "Choose a component from that lesson's unit, or none.")
        else:
            kind, _, pk = data.get("who", "").partition(":")
            data["pupil"] = self.pupils.get(pk) if kind == "pupil" else None
            data["group"] = self.groups.get(pk) if kind == "group" else None
        if not any(data.get(part, "").strip() for part in ("done_well", "develop", "how")):
            raise forms.ValidationError("Write at least one of done well, to develop or how.")
        try:
            data["recording_seconds"] = parse_at(data.get("recording_at", ""))
        except ValueError:
            self.add_error("recording_at", "Write the time as minutes:seconds, e.g. 1:42.")
        path = data.get("recording_path", "").strip()
        if data.get("recording_seconds") is not None and not path:
            self.add_error("recording_at", "A time needs the recording it's in.")
        if path:
            pupils = [data["pupil"]] if data["pupil"] else [m.pupil for m in data["group"].members.select_related("pupil")] if data["group"] else []
            refused = [str(p) for p in pupils if not p.recording_permitted]
            if refused:
                self.add_error("recording_path", f"Recordings aren't permitted for {', '.join(refused)}.")
        return data

    def save(self):
        data = self.cleaned_data
        return Feedback.objects.create(
            session=self.session, pupil=data["pupil"], group=data["group"], component=data.get("component"),
            done_well=data["done_well"].strip(), develop=data["develop"].strip(), how=data["how"].strip(),
            recording_path=data["recording_path"].strip(), recording_seconds=data.get("recording_seconds"),
        )
