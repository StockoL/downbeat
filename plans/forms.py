from django import forms

from .models import LessonPlan, PlanActivity, Resource, Scheme, Unit

AREA = {"rows": 3}


class SchemeForm(forms.ModelForm):
    class Meta:
        model = Scheme
        fields = ["name", "year_group"]


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ["name", "order", "lessons_planned", "purpose", "assessment_notes", "check_responses"]
        widgets = {"purpose": forms.Textarea(attrs=AREA), "assessment_notes": forms.Textarea(attrs=AREA)}
        labels = {"check_responses": "Record each pupil's hinge answer"}


class LessonForm(forms.ModelForm):
    class Meta:
        model = LessonPlan
        fields = ["order", "objective", "starter", "main", "assessment", "differentiation", "homework"]
        widgets = {f: forms.Textarea(attrs=AREA) for f in ["starter", "main", "assessment", "differentiation", "homework"]}


ActivityFormSet = forms.inlineformset_factory(
    LessonPlan, PlanActivity, fields=["order", "text", "minutes"], extra=3, can_delete=True,
    widgets={"order": forms.NumberInput(attrs={"min": 0, "max": 99}), "minutes": forms.NumberInput(attrs={"min": 1, "max": 120})},
)

ResourceFormSet = forms.inlineformset_factory(
    LessonPlan, Resource, fields=["title", "path_or_url", "needs_print", "copies", "setup_note"], extra=1, can_delete=True,
    labels={"path_or_url": "Where it lives", "needs_print": "Print"},
)
