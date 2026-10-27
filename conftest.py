import pytest
from django.test import Client

from rooms.models import Room
from timetable.models import Class, Pupil, Timetable

PASSWORD = "a long test password"


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    """Real hashing is deliberately slow; tests don't need it."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def teacher(django_user_model):
    return django_user_model.objects.create_user("teacher", password=PASSWORD)


@pytest.fixture
def client(db, teacher):
    """Signed in as the teacher, as every page but login and first-run setup requires."""
    signed_in = Client()
    signed_in.force_login(teacher)
    return signed_in


@pytest.fixture
def anon_client(db):
    return Client()


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
