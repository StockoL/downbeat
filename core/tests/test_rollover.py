import datetime
import json
import uuid

import pytest
from django.utils import timezone

from assessment.models import Component, Observation, Strand
from core import data, rollover
from notes.models import Note
from plans.models import Scheme, SessionReflection, Unit
from pupils.models import FlagType, Group, PupilFlag, Relationship
from rooms.models import Seat, SeatingPlan
from timetable.models import Class, Pupil, Session, Slot

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


@pytest.fixture
def backups(monkeypatch, tmp_path):
    """
    The rollover's backup, recorded rather than run: SQLite's online backup waits forever on the open
    transaction a test runs inside. The backup itself is tested in test_data.py.
    """
    made = []

    def backup():
        made.append(tmp_path / f"downbeat-{len(made)}.sqlite3")
        return made[-1]

    monkeypatch.setattr(data, "backup", backup)
    return made


@pytest.fixture
def year(timetable, klass, room, pupils, backups):
    """A year about to end: a slot, a lesson taught, one to come with nothing in it and one with a note."""
    Slot.objects.create(timetable=timetable, day=0, period="P1", room=room, klass=klass)
    taught = Session.objects.create(date=TODAY - datetime.timedelta(days=3), period="P1", klass=klass, room=room)
    empty = Session.objects.create(date=TODAY + datetime.timedelta(days=5), period="P1", klass=klass, room=room)
    noted = Session.objects.create(date=TODAY + datetime.timedelta(days=6), period="P1", klass=klass, room=room)
    Note.objects.create(session=noted, pupil=pupils[2], text="Bring the recorder back")
    open_action = Note.objects.create(session=taught, pupil=pupils[0], text="Chase homework", actionable=True)
    carried = Note.objects.create(session=taught, pupil=pupils[1], text="Return the ukulele", actionable=True)
    old = FlagType.objects.create(label="Hearing", colour=1)
    stale = PupilFlag.objects.create(pupil=pupils[0], flag_type=old, since=TODAY - datetime.timedelta(days=500))
    fresh = PupilFlag.objects.create(pupil=pupils[1], flag_type=old, since=TODAY - datetime.timedelta(days=30))
    a, b = sorted(pupils[:2], key=lambda p: p.pk)
    apart = Relationship.objects.create(pupil_a=a, pupil_b=b, kind="keep_apart", since=TODAY - datetime.timedelta(days=400))
    group = Group.objects.create(klass=klass, name="Band 1", started=TODAY - datetime.timedelta(days=60))
    unit = Unit.objects.create(scheme=Scheme.objects.create(name="Y8"), name="Blues")
    component = Component.objects.create(unit=unit, text="Steady pulse", strand=Strand.objects.create(name="Performing"), next_step_default="x")
    seen = Observation.objects.create(session=taught, pupil=pupils[0], component=component, state="secure", next_step="x")
    return locals()


def roll(client, year, **choices):
    pupils = year["pupils"]
    form = {"archive": [year["klass"].pk], "keep_flag": [year["fresh"].pk], "keep_relationship": [],
            "carry": [year["carried"].pk], "leaving": [pupils[2].pk], **{f"year-{p.pk}": "9" for p in pupils}, **choices}
    return client.post("/settings/rollover/", form, follow=True)


def test_the_page_asks_with_sensible_defaults(client, year):
    page = client.get("/settings/rollover/").content.decode()
    assert f'name="archive" value="{year["klass"].pk}" checked' in page
    assert f'name="year-{year["pupils"][0].pk}" value="9"' in page  # Year 8 moves to Year 9
    assert "over a year old" in page and "Chase homework" in page
    assert "Hearing" not in page  # flag labels are on the pupil page only (rule 8)
    found = rollover.preview()
    assert {row["flag"].pk: row["stale"] for row in found["flags"]} == {year["stale"].pk: True, year["fresh"].pk: False}


def test_rolling_over_archives_carries_forward_and_reviews(client, year, backups):
    klass, pupils = year["klass"], year["pupils"]
    response = roll(client, year)
    assert "Rolled over, after a backup" in response.content.decode()
    assert len(backups) == 1  # backed up first

    klass.refresh_from_db()
    assert klass.archived_on == TODAY and not Slot.objects.exists()
    assert Session.objects.filter(pk=year["taught"].pk).exists()
    assert not Session.objects.filter(pk=year["empty"].pk).exists()
    assert Session.objects.get(pk=year["noted"].pk).status == Session.CANCELLED  # something recorded: kept, cancelled
    assert Group.objects.get().ended == TODAY

    assert Note.objects.get(pk=year["open_action"].pk).done_at is not None
    assert Note.objects.get(pk=year["carried"].pk).done_at is None

    assert [p.year_group for p in Pupil.objects.filter(pk__in=[pupils[0].pk, pupils[1].pk])] == [9, 9]
    leaver = Pupil.objects.get(pk=pupils[2].pk)
    assert (leaver.left_on, leaver.year_group) == (TODAY, 8)

    assert list(PupilFlag.objects.all()) == [year["fresh"]]
    assert not Relationship.objects.exists()
    assert Observation.objects.filter(pk=year["seen"].pk, pupil=pupils[0]).exists()  # the timeline crosses the year


def test_no_backup_no_rollover(client, year, monkeypatch):
    def fail(*args, **kwargs):
        raise data.BackupFailed("the disk is full")

    monkeypatch.setattr(data, "backup", fail)
    response = roll(client, year)
    assert "the disk is full" in response.content.decode()
    year["klass"].refresh_from_db()
    assert year["klass"].archived_on is None


def test_an_archived_class_is_read_only(client, year):
    roll(client, year)
    klass, taught = year["klass"], year["taught"]
    op = {"op_id": str(uuid.uuid4()), "type": "note.add", "id": str(uuid.uuid4()), "session": str(taught.pk),
          "pupil": str(year["pupils"][0].pk), "text": "late", "at": timezone.now().isoformat()}
    result = client.post("/sync/", json.dumps({"ops": [op]}), content_type="application/json").json()
    assert "archived" in result["rejected"][0]["reason"]

    plan = SeatingPlan.objects.create(klass=klass, room=year["room"], name="Plan", active_from=TODAY)
    seat = Seat.objects.create(room=year["room"], x=0, y=0)
    response = client.post(f"/plan/seating/{plan.pk}/move/", {"pupil": year["pupils"][0].pk, "seat": seat.pk})
    assert response.status_code == 409 and not plan.assignments.exists()

    client.post(f"/sweep/{taught.pk}/", {"text": "Too late"})
    assert not SessionReflection.objects.filter(session=taught).exists()
    assert "is archived" in client.get(f"/room/{taught.pk}/").content.decode()


def test_archived_classes_and_leavers_leave_the_working_lists(client, year):
    roll(client, year)
    klass = year["klass"]
    home = client.get("/pupils/").content.decode()
    assert "Archived classes" in home and home.index("Archived classes") < home.index(str(klass))
    assert str(klass) not in client.get("/plan/").content.decode().split("<main", 1)[1]
    other = Class.objects.create(name="9A Mu", year_group=9)
    page = client.get(f"/settings/classes/{other.pk}/").content.decode()
    assert str(year["pupils"][0]) in page and str(year["pupils"][2]) not in page  # the leaver isn't offered


def test_bringing_a_class_back(client, year):
    roll(client, year)
    client.post(f"/settings/classes/{year['klass'].pk}/unarchive/")
    year["klass"].refresh_from_db()
    assert year["klass"].archived_on is None


# --- Next year's lists reuse the pupils who stay ---

def paste(client, klass, names):
    return client.post(f"/settings/classes/{klass.pk}/", {"add_pupils": "", "names": names}, follow=True)


def test_pasting_next_years_list_reuses_a_continuing_pupil(client, timetable, pupils):
    for p in pupils:
        p.year_group = 9
        p.save()
    nine = Class.objects.create(name="9A Mu", year_group=9)
    paste(client, nine, "Aleya Khan\nNew Pupil")
    assert Pupil.objects.filter(first_name="Aleya").count() == 1
    assert set(nine.pupils.values_list("first_name", flat=True)) == {"Aleya", "New"}


def test_pasting_makes_a_new_pupil_for_another_year_or_a_leaver(client, timetable, pupils):
    seven = Class.objects.create(name="7A Mu", year_group=7)
    paste(client, seven, "Aleya K")  # an Aleya K in Year 7 is someone else
    assert Pupil.objects.filter(first_name="Aleya").count() == 2
    Pupil.objects.filter(first_name="Jojo").update(left_on=TODAY)
    eight = Class.objects.create(name="8B Mu", year_group=8)
    paste(client, eight, "Jojo P")
    assert Pupil.objects.filter(first_name="Jojo").count() == 2


def test_pasting_skips_a_name_that_matches_two_pupils(client, timetable, pupils):
    Pupil.objects.create(first_name="Aleya", surname_initial="K", year_group=8)
    eight = Class.objects.create(name="8B Mu", year_group=8)
    response = paste(client, eight, "Aleya K")
    assert "More than one pupil matches" in response.content.decode() and not eight.pupils.exists()
