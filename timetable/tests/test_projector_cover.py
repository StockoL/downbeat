import datetime

import pytest
from reportlab import rl_config

from notes.models import Note, NoteType, SpokenTo
from rooms.models import Seat, SeatAssignment, SeatingPlan
from timetable.models import Session, SessionAttendance

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 11, 2)


@pytest.fixture
def busy_lesson(timetable, klass, room, pupils):
    """A lesson with everything the room view shows: notes, actions, spoken-to, absence."""
    plan = SeatingPlan.objects.create(klass=klass, room=room, active_from=D)
    for i, pupil in enumerate(pupils[:2]):
        SeatAssignment.objects.create(seating_plan=plan, seat=Seat.objects.create(room=room, x=i * 100, y=0), pupil=pupil)
    Seat.objects.create(room=room, x=300, y=0)  # an empty seat
    session = Session.objects.create(date=D, period="P1", klass=klass, room=room)
    note_type = NoteType.objects.create(label="Chase homework", icon="!", is_actionable_default=True)
    Note.objects.create(session=session, pupil=pupils[0], note_type=note_type, actionable=True)
    Note.objects.create(session=session, pupil=pupils[1], text="Private remark")
    SpokenTo.objects.create(session=session, pupil=pupils[0])
    SessionAttendance.objects.create(session=session, pupil=pupils[1], present=False)
    return session


def test_room_view_reaches_both_from_the_overflow_menu_only(client, busy_lesson):
    html = client.get(f"/room/{busy_lesson.pk}/").content.decode()
    menu = html.split('class="dropdown"')[1].split("</div>")[0]
    assert f"/room/{busy_lesson.pk}/projector/" in menu and f"/room/{busy_lesson.pk}/cover.pdf" in menu
    outside = html.replace(menu, "")
    assert "/projector/" not in outside and "cover.pdf" not in outside


def test_projector_shows_names_and_nothing_else(client, busy_lesson, pupils):
    html = client.get(f"/room/{busy_lesson.pk}/projector/").content.decode()
    assert "Aleya K" in html and "Jojo P" in html
    for leak in ["Chase homework", "Private remark", "seat__marks", "seat__badges", "seat__unread",
                 "data-spoken", "data-absent", "data-missed", "hx-get", "Log"]:
        assert leak not in html, leak
    assert 'data-canvas="projector"' in html


def test_cover_pdf_shows_names_and_nothing_else(client, busy_lesson, pupils, monkeypatch):
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    response = client.get(f"/room/{busy_lesson.pk}/cover.pdf")
    assert response["Content-Type"] == "application/pdf"
    assert 'filename="cover-8x-mu-m2-2026-11-02.pdf"' in response["Content-Disposition"]
    pdf = response.content
    assert pdf.startswith(b"%PDF")
    assert b"(Aleya K)" in pdf and b"(Jojo P)" in pdf
    assert b"Not seated: Sam T" in pdf
    for leak in [b"Chase homework", b"Private remark", b"absent", b"spoken"]:
        assert leak not in pdf, leak


def test_cover_pdf_for_a_room_with_no_plan_is_the_empty_layout(client, timetable, klass, room, pupils, monkeypatch):
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    Seat.objects.create(room=room, x=0, y=0)
    session = Session.objects.create(date=D, period="P1", klass=klass, room=room)
    pdf = client.get(f"/room/{session.pk}/cover.pdf").content
    assert pdf.startswith(b"%PDF") and b"Not seated: Aleya K, Jojo P, Sam T" in pdf
