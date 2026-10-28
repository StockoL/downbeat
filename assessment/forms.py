from django import forms

from .models import Check

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
