import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.utils import timezone

from notes.models import Note
from rooms.models import SeatingPlan
from timetable.models import Class, Pupil, Session, Timetable

pytestmark = pytest.mark.django_db


def test_seed_demo_builds_a_usable_school(capsys):
    call_command("seed_demo")
    assert "Demo data in" in capsys.readouterr().out
    assert Timetable.objects.count() == 1
    assert Class.objects.filter(kind=Class.CO_CURRICULAR).count() == 1
    assert Pupil.objects.count() > 80
    assert all(len(p.surname_initial) == 1 for p in Pupil.objects.all())
    assert Session.objects.filter(date=timezone.localdate()).exists() or timezone.localdate().weekday() >= 5
    assert Note.objects.open_actions().exists()

    moved = Session.objects.get(status=Session.MOVED)
    assert SeatingPlan.current(moved.klass, moved.room, moved.date) is None  # the zone-copy offer shows


def test_seed_demo_is_the_same_school_every_time():
    call_command("seed_demo")
    first = sorted(str(p) for p in Pupil.objects.all())
    call_command("seed_demo", "--reset")
    assert sorted(str(p) for p in Pupil.objects.all()) == first


def test_seed_demo_refuses_a_database_with_data(timetable):
    with pytest.raises(CommandError, match="already has data"):
        call_command("seed_demo")


@pytest.mark.filterwarnings("ignore:Overriding setting DATABASES")
def test_seed_demo_reset_refuses_the_real_database(settings, timetable):
    with override_settings(DATABASES={**settings.DATABASES, "default": {**settings.DATABASES["default"], "NAME": settings.BASE_DIR / "db.sqlite3"}}):
        with pytest.raises(CommandError, match="won't touch db.sqlite3"):
            call_command("seed_demo", "--reset")
    assert Timetable.objects.filter(pk=timetable.pk).exists()
