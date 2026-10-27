import json
import sqlite3

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session as BrowserSession
from django.core.management import call_command

from core import data
from notes.models import Note, NoteType
from timetable.models import Pupil, Session, Timetable

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def school(timetable, klass, room, pupils):
    session = Session.objects.create(date="2026-11-02", period="P1", klass=klass, room=room)
    Note.objects.create(session=session, pupil=pupils[0], note_type=NoteType.objects.create(label="House point"))
    return session


def test_backup_is_a_complete_checked_copy(school, tmp_path):
    path = data.backup(tmp_path, keep=5)
    assert path.exists() and path.name.startswith("downbeat-")
    copy = sqlite3.connect(path)
    try:
        assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert copy.execute("SELECT count(*) FROM timetable_pupil").fetchone()[0] == 3
        assert copy.execute("SELECT count(*) FROM notes_note").fetchone()[0] == 1
    finally:
        copy.close()


def test_backup_keeps_only_the_newest(school, tmp_path):
    for stamp in ["20260101-000000", "20260102-000000", "20260103-000000"]:
        (tmp_path / f"downbeat-{stamp}.sqlite3").write_bytes(b"old")
    newest = data.backup(tmp_path, keep=2)
    remaining = data.list_backups(tmp_path)
    assert remaining == [newest, tmp_path / "downbeat-20260103-000000.sqlite3"]


def test_backup_command(school, tmp_path, capsys):
    call_command("backup", "--dest", str(tmp_path))
    assert "Backed up to" in capsys.readouterr().out
    assert len(data.list_backups(tmp_path)) == 1


def test_export_contains_every_row_and_loads_back(school, tmp_path):
    exported = json.loads(data.export_json())
    models = {row["model"] for row in exported}
    assert {"timetable.pupil", "timetable.session", "notes.note", "notes.notetype", "rooms.room"} <= models
    assert not any(row["model"].startswith(("sessions.", "contenttypes.")) for row in exported)

    path = tmp_path / "export.json"
    call_command("export_json", str(path))
    data.delete_all()
    call_command("loaddata", str(path))
    assert Pupil.objects.count() == 3 and Note.objects.count() == 1


def test_delete_all_leaves_nothing_and_returns_to_setup(client, school, teacher):
    client.get("/")  # make a browser session
    data.delete_all()
    for model in data.APP_MODELS:
        assert not model.objects.exists(), model
    assert not BrowserSession.objects.exists()
    assert client.get("/").url.startswith("/login/")  # every device is signed out
    client.force_login(teacher)  # the account is kept, so signing back in leads to setup
    assert client.get("/").url == "/setup/"


# --- Settings → Data views ---

def test_data_page_renders(client, school, settings, tmp_path):
    settings.BACKUP_DIR = tmp_path
    assert client.get("/settings/data/").status_code == 200


def test_back_up_now_button(client, school, settings, tmp_path):
    settings.BACKUP_DIR = tmp_path
    client.post("/settings/data/backup/")
    assert len(data.list_backups(tmp_path)) == 1


def test_export_download(client, school):
    response = client.get("/settings/data/export/")
    assert response["Content-Type"] == "application/json"
    assert "attachment" in response["Content-Disposition"]
    assert any(row["model"] == "timetable.pupil" for row in json.loads(response.content))


def test_delete_all_needs_the_phrase(client, school):
    client.post("/settings/data/delete-all/", {"confirm": "yes"})
    assert Timetable.objects.exists()
    response = client.post("/settings/data/delete-all/", {"confirm": "  Delete Everything "})
    assert response.url == "/setup/"
    assert not Timetable.objects.exists() and not Pupil.objects.exists()


def test_delete_all_needs_post(client, school):
    assert client.get("/settings/data/delete-all/").status_code == 405
    assert Timetable.objects.exists()


def test_delete_all_and_export_cover_every_downbeat_table():
    """A table added in a later phase must be added to delete-all and export, or this fails."""
    from django.apps import apps

    ours = {m for m in apps.get_models() if m._meta.app_label in data.EXPORT_APPS}
    assert ours == set(data.APP_MODELS)
    local_apps = {"core", *data.EXPORT_APPS}
    for config in apps.get_app_configs():
        ours_on_disk = config.path.startswith(str(settings.BASE_DIR)) and "site-packages" not in config.path
        if ours_on_disk and list(config.get_models()):
            assert config.label in local_apps, f"{config.label} isn't exported or deleted"
