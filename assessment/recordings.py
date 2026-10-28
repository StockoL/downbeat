"""
Rule 15: recordings are kept only for pupils whose families agreed, reused as exemplars only with
the separate reuse permission, and gone when a pupil's delete-by date passes. Downbeat holds paths,
not files, so removing a recording here means removing the reference and telling the teacher which
files to delete from the folder.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from pupils.models import GroupMember
from timetable.models import Pupil

from .models import Exemplar, Feedback, Observation


def _expired(today):
    """Pupils whose recordings may not be kept: past their delete-by date, or never permitted."""
    return Pupil.objects.filter(Q(recordings_delete_by__lte=today) | Q(recording_permitted=False))


def due(today=None):
    """What has to go, as querysets: observations, feedback and exemplars holding a recording they mayn't."""
    today = today or timezone.localdate()
    expired = _expired(today)
    groups = GroupMember.objects.filter(pupil__in=expired).values("group_id")
    reuse_ended = Pupil.objects.filter(Q(pk__in=expired) | Q(exemplar_reuse_permitted=False))
    return {
        "observations": Observation.objects.filter(pupil__in=expired).exclude(recording_path=""),
        "feedback": Feedback.objects.filter(Q(pupil__in=expired) | Q(group__in=groups)).exclude(recording_path=""),
        "exemplars": Exemplar.objects.filter(source_pupil__in=reuse_ended),
    }


def paths(found):
    """Every recording path in what was found, once each, for the teacher to delete."""
    seen = []
    for rows in found.values():
        for path in rows.values_list("recording_path", flat=True):
            if path not in seen:
                seen.append(path)
    return seen


@transaction.atomic
def purge(today=None):
    """
    Removes the references. An observation kept only for its recording goes; one with a next step
    keeps its next step. Returns the paths that were referenced, for deleting the files.
    """
    found = due(today)
    removed = paths(found)
    now = timezone.now()
    found["observations"].filter(next_step="").delete()
    found["observations"].update(recording_path="", updated_at=now)
    found["feedback"].update(recording_path="", recording_seconds=None, updated_at=now)
    found["exemplars"].delete()
    return removed
