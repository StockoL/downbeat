import pytest

from rooms.models import Room
from timetable.models import Class, Pupil, Timetable


@pytest.fixture
def timetable(db):
    """A set-up install, so the first-run redirect stays out of the way."""
    return Timetable.objects.create(
        name="Test",
        week_cycle=2,
        periods=[
            {"label": "P1", "start": "08:50", "end": "09:50"},
            {"label": "P2", "start": "09:50", "end": "10:50"},
        ],
    )


@pytest.fixture
def room(db):
    return Room.objects.create(name="M2")


@pytest.fixture
def klass(db):
    return Class.objects.create(name="8X Mu", year_group=8)


@pytest.fixture
def pupils(klass):
    made = [Pupil.objects.create(first_name=n, surname_initial=i, year_group=8) for n, i in [("Aleya", "K"), ("Jojo", "P"), ("Sam", "T")]]
    klass.pupils.add(*made)
    return made
