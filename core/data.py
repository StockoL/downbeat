"""
Whole-database jobs from the data rules: nightly backup, full JSON export, delete-all.
The laptop's SQLite file is the only copy of the data, so these are its safety net.
"""

import io
import sqlite3
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session as BrowserSession
from django.core.management import call_command
from django.db import connection, transaction
from django.utils import timezone

from notes.models import Note, NoteType, SpokenTo
from pupils.models import FlagType, PupilFlag, Relationship
from rooms.models import Room, Seat, SeatAssignment, SeatingPlan
from timetable.models import Class, Pupil, Session, SessionAttendance, Slot, Timetable

# Every Downbeat table, children before parents, so deleting in this order never trips a protected key.
APP_MODELS = [
    SpokenTo, Note, SessionAttendance, SeatAssignment, SeatingPlan, Session, Slot,
    Seat, Room, Relationship, PupilFlag, FlagType, Class, Pupil, NoteType, Timetable,
]
EXPORT_APPS = ["timetable", "rooms", "notes", "pupils"]
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


@transaction.atomic
def delete_all():
    """Remove every Downbeat row and every browser session. The app returns to first-run setup."""
    for model in APP_MODELS:
        model.objects.all().delete()
    BrowserSession.objects.all().delete()
