import pytest

from timetable.models import Timetable


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
