"""Pupils → Loans: the weekly headphone hunt."""

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from timetable.forms import DATE
from timetable.models import Pupil

from .models import Loan, LoanItem


class LendForm(forms.Form):
    item = forms.ModelChoiceField(queryset=LoanItem.objects.none())
    pupil = forms.ModelChoiceField(queryset=Pupil.objects.all())
    due = forms.DateField(widget=DATE, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = LoanItem.objects.exclude(pk__in=Loan.objects.filter(returned_at__isnull=True).values("item"))


class ItemForm(forms.ModelForm):
    class Meta:
        model = LoanItem
        fields = ["name", "kind", "identifier", "condition_note"]
        labels = {"condition_note": "Condition"}


def loans(request):
    action = request.POST.get("action") if request.method == "POST" else None
    lend = LendForm(request.POST if action == "lend" else None, prefix="lend")
    item_form = ItemForm(request.POST if action == "item" else None, prefix="item")
    if action == "lend" and lend.is_valid():
        Loan.objects.create(out_at=timezone.now(), **lend.cleaned_data)
        messages.success(request, f"Lent {lend.cleaned_data['item']} to {lend.cleaned_data['pupil']}.")
        return redirect("loans")
    if action == "item" and item_form.is_valid():
        item_form.save()
        return redirect("loans")

    today = timezone.localdate()
    out = list(Loan.objects.filter(returned_at__isnull=True).select_related("item", "pupil"))
    # Overdue first, then by due date; loans with no due date last.
    out.sort(key=lambda loan: (loan.due is None, loan.due or today))
    for loan in out:
        loan.overdue = loan.due is not None and loan.due < today
    on_shelf = LoanItem.objects.exclude(pk__in=[loan.item_id for loan in out])
    return render(request, "pupils/loans.html", {
        "nav": "pupils", "out": out, "on_shelf": on_shelf, "lend": lend, "item_form": item_form,
    })


@require_POST
def loan_return(request, pk):
    loan = get_object_or_404(Loan.objects.select_related("item"), pk=pk, returned_at__isnull=True)
    loan.returned_at = timezone.now()
    loan.condition_on_return = request.POST.get("condition", "").strip()[:200]
    loan.save(update_fields=["returned_at", "condition_on_return", "updated_at"])
    if loan.condition_on_return:
        loan.item.condition_note = loan.condition_on_return
        loan.item.save(update_fields=["condition_note", "updated_at"])
    messages.success(request, f"{loan.item} is back.")
    return redirect("loans")
