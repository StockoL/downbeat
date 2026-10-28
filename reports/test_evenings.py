import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from notes.models import Note
from reports import evenings
from reports.models import EveningSlot, ParentsEvening
from timetable.models import Pupil, Session

pytestmark = pytest.mark.django_db

T = datetime.time


@pytest.fixture
def evening(timetable):
    evening = ParentsEvening.objects.create(name="Year 9", date=timezone.localdate() + datetime.timedelta(days=7),
                                            start=T(17), end=T(18), slot_minutes=10, break_times=[["17:30", "17:40"]])
    evenings.generate_slots(evening)
    return evening


def times(evening):
    return [s.start_time for s in evening.slots.all()]


# --- Slots ---

def test_slots_step_through_the_evening_and_miss_the_break(evening):
    assert times(evening) == [T(17), T(17, 10), T(17, 20), T(17, 40), T(17, 50)]


def test_making_slots_again_keeps_bookings(evening, pupils):
    evenings.book(evening.slots.get(start_time=T(17, 50)), pupils[0])
    evening.end, evening.slot_minutes = T(17, 30), 15
    evening.save()
    evenings.generate_slots(evening)
    assert times(evening) == [T(17), T(17, 15), T(17, 50)]  # 17:50 is booked, so it stays


def test_a_new_evening_from_the_form(client, timetable):
    client.post("/pupils/evenings/", {"name": "Year 8", "date": "2026-11-12", "start": "16:00", "end": "17:00",
                                      "slot_minutes": "5", "breaks": "16:30-16:35"})
    evening = ParentsEvening.objects.get()
    assert evening.break_times == [["16:30", "16:35"]] and evening.slots.count() == 11
    response = client.post("/pupils/evenings/", {"name": "Bad", "date": "2026-11-12", "start": "17:00", "end": "16:00",
                                                 "slot_minutes": "5", "breaks": "soon"})
    assert response.status_code == 200 and ParentsEvening.objects.count() == 1


# --- Booking ---

def test_one_time_per_family_and_one_family_per_time(evening, pupils):
    first, second = evening.slots.all()[:2]
    evenings.book(first, pupils[0])
    with pytest.raises(evenings.Refused):
        evenings.book(second, pupils[0])
    with pytest.raises(evenings.Refused):
        evenings.book(first, pupils[1])


def test_booking_from_the_class_list_in_two_taps(client, evening, klass, pupils):
    assert f"/pupils/{pupils[0].pk}/book/" in client.get(f"/pupils/class/{klass.pk}/").content.decode()
    page = client.get(f"/pupils/{pupils[0].pk}/book/?back=/pupils/class/{klass.pk}/").content.decode()
    assert "17:40" in page
    slot = evening.slots.get(start_time=T(17, 40))
    response = client.post(f"/pupils/evenings/{evening.pk}/book/",
                           {"slot": slot.pk, "pupil": pupils[0].pk, "next": f"/pupils/class/{klass.pk}/"})
    assert response.url == f"/pupils/class/{klass.pk}/"
    assert EveningSlot.objects.get(pk=slot.pk).pupil == pupils[0]
    assert "Booked at" in client.get(f"/pupils/{pupils[0].pk}/book/").content.decode()


def test_booking_never_returns_to_another_site(client, evening, pupils):
    slot = evening.slots.first()
    response = client.post(f"/pupils/evenings/{evening.pk}/book/", {"slot": slot.pk, "pupil": pupils[0].pk, "next": "https://elsewhere.test/"})
    assert response.url == f"/pupils/evenings/{evening.pk}/"


def test_freeing_a_time(client, evening, pupils):
    slot = evening.slots.first()
    evenings.book(slot, pupils[0])
    client.post(f"/pupils/evenings/{evening.pk}/slots/{slot.pk}/free/")
    assert EveningSlot.objects.get(pk=slot.pk).pupil is None


def test_booking_from_the_schools_csv(client, evening, pupils):
    first = pupils[0]
    csv = (f"Time,Pupil\n17:00,{first.first_name} {first.surname_initial}ingsley\n17.10,Nobody Here\n19:00,{pupils[1].first_name} {pupils[1].surname_initial}\n"
           f"17:20,{first.first_name} {first.surname_initial}\n")
    response = client.post(f"/pupils/evenings/{evening.pk}/import/",
                           {"file": SimpleUploadedFile("bookings.csv", csv.encode("utf-8-sig"))}, follow=True)
    page = response.content.decode()
    assert EveningSlot.objects.get(start_time=T(17)).pupil == first
    assert "Booked 1 from the file" in page
    assert "Row 3" in page and "Row 4" in page and "Row 5" in page  # no match, no 19:00 slot, already booked


def test_a_name_matches_only_when_it_is_unique(evening, pupils):
    Pupil.objects.create(first_name=pupils[0].first_name, surname_initial=pupils[0].surname_initial)
    booked, problems = evenings.import_bookings(evening, f"17:00,{pupils[0]}")
    assert booked == 0 and "no single pupil" in problems[0]


# --- The night ---

def test_a_family_who_did_not_come_becomes_an_action_once(client, evening, klass, room, pupils):
    lesson = Session.objects.create(date=timezone.localdate(), period="P1", klass=klass, room=room)
    slot = evening.slots.first()
    evenings.book(slot, pupils[0])
    page = client.get(f"/pupils/evenings/{evening.pk}/tonight/").content.decode()
    assert str(pupils[0]) in page and f"/pupils/{pupils[0].pk}/" in page
    client.post(f"/pupils/evenings/{evening.pk}/tonight/{slot.pk}/", {"attended": "no"})
    client.post(f"/pupils/evenings/{evening.pk}/tonight/{slot.pk}/", {"attended": "no"})
    note = Note.objects.get()
    assert (note.session, note.pupil, note.actionable) == (lesson, pupils[0], True)
    assert note.text.startswith("Follow up with parents")
    assert EveningSlot.objects.get(pk=slot.pk).follow_up_note == note.text


def test_a_family_who_came_and_a_note_from_the_night(client, evening, pupils):
    slot = evening.slots.first()
    evenings.book(slot, pupils[0])
    client.post(f"/pupils/evenings/{evening.pk}/tonight/{slot.pk}/", {"attended": "yes"})
    client.post(f"/pupils/evenings/{evening.pk}/tonight/{slot.pk}/", {"note": "Wants to join the band"})
    slot.refresh_from_db()
    assert (slot.attended, slot.on_the_night_note) == (True, "Wants to join the band")
    assert not Note.objects.exists()


def test_deleting_an_evening(client, evening):
    client.post(f"/pupils/evenings/{evening.pk}/delete/")
    assert not ParentsEvening.objects.exists() and not EveningSlot.objects.exists()
