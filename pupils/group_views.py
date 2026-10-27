"""Plan → a class's groups. Groups are ended, not deleted, so "which part did they play" stays answerable."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from timetable.models import Class

from .forms import GroupForm, MemberForm
from .models import Group, GroupMember


def class_groups(request, pk):
    klass = get_object_or_404(Class, pk=pk)
    form = GroupForm(request.POST or None, klass=klass, initial={"started": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        group = form.save()
        messages.success(request, f"Added {group}.")
        return redirect("class_groups", pk=klass.pk)
    groups = klass.groups.prefetch_related("members__pupil")
    return render(request, "pupils/groups.html", {
        "nav": "plan",
        "klass": klass,
        "active": [{"group": g, "form": MemberForm(group=g)} for g in groups if g.ended is None],
        "ended": [g for g in groups if g.ended is not None],
        "form": form,
    })


@require_POST
def group_add_member(request, pk):
    group = get_object_or_404(Group, pk=pk)
    form = MemberForm(request.POST, group=group)
    if form.is_valid():
        form.save()
    else:
        messages.error(request, "That pupil is already in an active group.")
    return redirect("class_groups", pk=group.klass_id)


@require_POST
def group_member_role(request, pk):
    member = get_object_or_404(GroupMember.objects.select_related("group"), pk=pk)
    member.role = request.POST.get("role", "").strip()[:40]
    member.save(update_fields=["role", "updated_at"])
    return redirect("class_groups", pk=member.group.klass_id)


@require_POST
def group_remove_member(request, pk):
    member = get_object_or_404(GroupMember.objects.select_related("group"), pk=pk)
    member.delete()
    return redirect("class_groups", pk=member.group.klass_id)


@require_POST
def group_end(request, pk):
    group = get_object_or_404(Group, pk=pk)
    group.ended = timezone.localdate()
    group.save(update_fields=["ended", "updated_at"])
    messages.success(request, f"Ended {group}. It stays in the history below.")
    return redirect("class_groups", pk=group.klass_id)
