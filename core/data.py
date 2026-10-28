"""
Whole-database jobs from the data rules: nightly backup, full JSON export, delete-all.
The laptop's SQLite file is the only copy of the data, so these are its safety net.
"""

import io
import json
import sqlite3
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session as BrowserSession
from django.core.management import call_command
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone

from assessment.models import Band, Check, CheckResponse, Component, Exemplar, Feedback, FeedbackCode, Observation, Strand
from notes.models import ChecklistItem, ChecklistTick, Goal, Note, NoteType, SpokenTo
from plans.models import ActivityStatus, LessonPlan, PlanActivity, PrepItem, Resource, Scheme, SessionReflection, Unit
from pupils.models import FlagType, Group, GroupMember, Loan, LoanItem, PupilFlag, Relationship
from reports.models import SummativeJudgement
from rooms.models import Room, Seat, SeatAssignment, SeatingPlan
from timetable.models import Class, Pupil, PupilRotation, Rotation, Session, SessionAttendance, Slot, Timetable

# Every Downbeat table, children before parents, so deleting in this order never trips a protected key.
APP_MODELS = [
    # what happened in lessons (checks and observations first: they protect their session)
    SummativeJudgement, CheckResponse, Check, Feedback, Observation, PrepItem, SessionReflection, ActivityStatus,
    ChecklistTick, ChecklistItem, Goal, SpokenTo, Note, SessionAttendance,
    # seating and sessions
    SeatAssignment, SeatingPlan, Session, Slot, Seat, Room,
    # assessment
    Exemplar, FeedbackCode, Component, Strand, Band,
    # plans
    Resource, PlanActivity, LessonPlan, Unit, Scheme,
    # pupils' records
    Loan, LoanItem, PupilRotation, Rotation, GroupMember, Group, Relationship, PupilFlag, FlagType,
    # the frame
    Class, Pupil, NoteType, Timetable,
]
EXPORT_APPS = ["timetable", "rooms", "notes", "pupils", "plans", "assessment", "reports"]
BACKUP_GLOB = "downbeat-*.sqlite3"


class BackupFailed(Exception):
    pass


def backup(dest=None, keep=None):
    """
    Copy the live database with SQLite's online backup API (consistent even mid-write), check
    the copy's integrity, then keep only the newest `keep` backups. Returns the new file's path.
    """
    dest = Path(dest or settings.BACKUP_DIR)
    keep = keep or settings.BACKUP_KEEP
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"downbeat-{timezone.localtime():%Y%m%d-%H%M%S}.sqlite3"

    connection.ensure_connection()
    copy = sqlite3.connect(target)
    try:
        connection.connection.backup(copy)
        copy.execute("PRAGMA journal_mode=DELETE")  # one self-contained file, restorable by copying it back
        result = copy.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        copy.close()
    if result != "ok":
        target.unlink(missing_ok=True)
        raise BackupFailed(f"The copy failed its integrity check: {result}")

    for old in list_backups(dest)[keep:]:
        old.unlink()
    return target


def list_backups(dest=None):
    """Backups in the folder, newest first."""
    dest = Path(dest or settings.BACKUP_DIR)
    if not dest.exists():
        return []
    return sorted(dest.glob(BACKUP_GLOB), key=lambda p: p.name, reverse=True)


def export_json():
    """Every row Downbeat holds, as Django's JSON fixture format: readable, and loadable with loaddata."""
    out = io.StringIO()
    call_command("dumpdata", *EXPORT_APPS, indent=2, stdout=out)
    return out.getvalue()


def export_pupil(pupil):
    """
    Everything held about one pupil, for a subject access request (rule 15): their own row, their
    classes' names, and every row in Downbeat's tables that points at them, found by following each
    link to Pupil rather than a list, so a new table can't be missed. Group feedback they were part
    of is included. Other pupils appear only as ids.
    """
    from django.apps import apps
    from django.core import serializers

    rows = [pupil]
    for app in EXPORT_APPS:
        for model in apps.get_app_config(app).get_models():
            for field in model._meta.get_fields():
                if field.many_to_one and field.related_model is Pupil:
                    rows += model.objects.filter(**{field.name: pupil})
    groups = GroupMember.objects.filter(pupil=pupil).values("group_id")
    rows += Feedback.objects.filter(group__in=groups)
    return json.dumps({
        "format": "downbeat-pupil", "exported": timezone.now().isoformat(), "pupil": str(pupil),
        "classes": [str(c) for c in pupil.classes.all()],
        "records": serializers.serialize("python", rows),
    }, cls=DjangoJSONEncoder, indent=2)


@transaction.atomic
def delete_all():
    """Remove every Downbeat row and every browser session. The app returns to first-run setup."""
    for model in APP_MODELS:
        model.objects.all().delete()
    BrowserSession.objects.all().delete()
