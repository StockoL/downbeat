import datetime

import pytest

from timetable.models import Class, Pupil, Session, Slot

pytestmark = pytest.mark.django_db


@pytest.fixture
def slot(timetable, room, klass):
    return Slot.objects.create(timetable=timetable, week="A", day=0, period="P1", room=room, klass=klass)


@pytest.fixture
def session(slot):
    return Session.objects.create(date=datetime.date(2026, 11, 2), slot=slot, period="P1", room=slot.room, klass=slot.klass)


@pytest.mark.parametrize("url", [
    "/settings/", "/settings/timetable/", "/settings/slots/", "/settings/classes/",
    "/settings/pupils/", "/settings/sessions/",
])
def test_settings_pages_render(client, timetable, url):
    assert client.get(url).status_code == 200


# --- Timetable ---

def test_edit_timetable_saves_name_cycle_and_periods(client, timetable):
    response = client.post("/settings/timetable/", {
        "timetable-name": "Renamed", "timetable-week_cycle": "1",
        "periods-TOTAL_FORMS": "3", "periods-INITIAL_FORMS": "2",
        "periods-MIN_NUM_FORMS": "1", "periods-MAX_NUM_FORMS": "1000",
        "periods-0-label": "P1", "periods-0-start": "08:45", "periods-0-end": "09:45",
        "periods-1-label": "", "periods-1-start": "", "periods-1-end": "",
        "periods-2-label": "Lunch", "periods-2-start": "12:30", "periods-2-end": "13:15",
    })
    assert response.status_code == 302
    timetable.refresh_from_db()
    assert timetable.name == "Renamed" and timetable.week_cycle == 1
    assert [p["label"] for p in timetable.periods] == ["P1", "Lunch"]


# --- Slots ---

def test_add_slot(client, timetable, room, klass):
    response = client.post("/settings/slots/", {"week": "B", "day": "2", "period": "P2", "klass": klass.pk, "room": room.pk})
    assert response.status_code == 302
    slot = Slot.objects.get()
    assert (slot.timetable, slot.week, slot.day, slot.period) == (timetable, "B", 2, "P2")


def test_add_slot_rejects_unknown_period(client, timetable, room, klass):
    client.post("/settings/slots/", {"week": "A", "day": "0", "period": "P9", "klass": klass.pk, "room": room.pk})
    assert not Slot.objects.exists()


def test_one_week_timetable_slots_are_week_a(client, timetable, room, klass):
    timetable.week_cycle = 1
    timetable.save()
    client.post("/settings/slots/", {"day": "0", "period": "P1", "klass": klass.pk, "room": room.pk})
    assert Slot.objects.get().week == "A"


def test_edit_slot(client, slot):
    client.post(f"/settings/slots/{slot.pk}/", {"week": "A", "day": "4", "period": "P2", "klass": slot.klass.pk, "room": slot.room.pk})
    slot.refresh_from_db()
    assert (slot.day, slot.period) == (4, "P2")


def test_delete_slot_keeps_its_sessions(client, session):
    client.post(f"/settings/slots/{session.slot.pk}/delete/")
    assert not Slot.objects.exists()
    session.refresh_from_db()
    assert session.slot is None


def test_delete_needs_post(client, slot):
    assert client.get(f"/settings/slots/{slot.pk}/delete/").status_code == 405


# --- Classes ---

def test_add_class(client, timetable):
    response = client.post("/settings/classes/", {"name": "Choir", "kind": "co_curricular", "year_group": ""})
    klass = Class.objects.get()
    assert response.url == f"/settings/classes/{klass.pk}/"
    assert klass.kind == Class.CO_CURRICULAR and klass.year_group is None


def test_edit_class_details(client, timetable, klass):
    client.post(f"/settings/classes/{klass.pk}/", {"save_details": "", "name": "8X Music", "kind": "timetabled", "year_group": "8"})
    klass.refresh_from_db()
    assert klass.name == "8X Music"


def test_paste_pupils_keeps_only_the_surname_initial(client, timetable, klass):
    client.post(f"/settings/classes/{klass.pk}/", {
        "add_pupils": "", "names": "Aleya Khan\nMary Jane s\n\nCher\n",
    })
    names = sorted(str(p) for p in klass.pupils.all())
    assert names == ["Aleya K", "Mary Jane S"]
    assert not Pupil.objects.filter(first_name__icontains="Khan").exists()
    assert all(p.year_group == 8 for p in klass.pupils.all())


def test_add_existing_pupils_to_a_class(client, timetable, pupils):
    choir = Class.objects.create(name="Choir", kind=Class.CO_CURRICULAR)
    client.post(f"/settings/classes/{choir.pk}/", {"add_pupils": "", "names": "", "existing": [pupils[0].pk, pupils[2].pk]})
    assert set(choir.pupils.all()) == {pupils[0], pupils[2]}
    assert Pupil.objects.count() == 3


def test_remove_pupil_from_class_keeps_the_pupil(client, timetable, klass, pupils):
    client.post(f"/settings/classes/{klass.pk}/remove/{pupils[0].pk}/")
    assert pupils[0] not in klass.pupils.all()
    assert Pupil.objects.filter(pk=pupils[0].pk).exists()


def test_delete_class_without_sessions(client, slot):
    client.post(f"/settings/classes/{slot.klass.pk}/delete/")
    assert not Class.objects.exists() and not Slot.objects.exists()


def test_delete_class_with_sessions_is_refused(client, session):
    client.post(f"/settings/classes/{session.klass.pk}/delete/")
    assert Class.objects.exists()


# --- Pupils ---

def test_add_pupil(client, timetable):
    client.post("/settings/pupils/", {"first_name": "Aleya", "surname_initial": "k", "year_group": "8"})
    assert str(Pupil.objects.get()) == "Aleya K"


def test_add_pupil_rejects_more_than_an_initial(client, timetable):
    client.post("/settings/pupils/", {"first_name": "Aleya", "surname_initial": "Khan"})
    assert not Pupil.objects.exists()


def test_edit_pupil(client, timetable, pupils):
    pupil = pupils[0]
    client.post(f"/settings/pupils/{pupil.pk}/", {"first_name": "Aleya", "surname_initial": "K", "instrument": "Cello"})
    pupil.refresh_from_db()
    assert pupil.instrument == "Cello"


def test_delete_pupil(client, timetable, pupils):
    client.post(f"/settings/pupils/{pupils[0].pk}/delete/")
    assert Pupil.objects.count() == 2


# --- Sessions ---

def test_add_one_off_session(client, timetable, room, klass):
    client.post("/settings/sessions/", {
        "add_session": "", "date": "2026-11-03", "period": "P2", "klass": klass.pk, "room": room.pk, "status": "planned",
    })
    session = Session.objects.get()
    assert session.slot is None and session.period == "P2"


def test_edit_session_changes_room(client, session):
    from rooms.models import Room
    other = Room.objects.create(name="M3")
    client.post(f"/settings/sessions/{session.pk}/", {
        "date": "2026-11-02", "period": "P1", "klass": session.klass.pk, "room": other.pk, "status": "moved",
    })
    session.refresh_from_db()
    assert session.room == other and session.status == Session.MOVED


def test_delete_session(client, session):
    client.post(f"/settings/sessions/{session.pk}/delete/")
    assert not Session.objects.exists()


def test_generate_sessions_button(client, slot):
    # Mon 2 Nov 2026 is week A, so slot (A, Monday) lands on 2 Nov and 16 Nov, not 9 Nov.
    response = client.post("/settings/sessions/generate/", {"start": "2026-11-02", "end": "2026-11-20", "first_week": "A"})
    assert response.status_code == 302
    assert sorted(Session.objects.values_list("date", flat=True)) == [datetime.date(2026, 11, 2), datetime.date(2026, 11, 16)]


def test_generate_sessions_rejects_backwards_range(client, slot):
    client.post("/settings/sessions/generate/", {"start": "2026-11-20", "end": "2026-11-02", "first_week": "A"})
    assert not Session.objects.exists()
