import datetime

import pytest
from django.db import IntegrityError
from django.utils import timezone

from pupils.models import Loan, LoanItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def headphones(db):
    return LoanItem.objects.create(name="Headphones", kind="headphones", identifier="7")


def test_add_equipment(client, timetable):
    client.post("/pupils/loans/", {"action": "item", "item-name": "Ukulele", "item-kind": "ukulele", "item-identifier": "3"})
    assert str(LoanItem.objects.get()) == "Ukulele 3"


def test_lend_and_return_with_a_condition_note(client, timetable, pupils, headphones):
    client.post("/pupils/loans/", {"action": "lend", "lend-item": headphones.pk, "lend-pupil": pupils[0].pk, "lend-due": "2026-11-06"})
    loan = Loan.objects.get()
    assert loan.pupil == pupils[0] and loan.due == datetime.date(2026, 11, 6) and loan.returned_at is None
    assert "Headphones 7" in client.get(f"/pupils/{pupils[0].pk}/").content.decode()  # on the pupil page
    client.post(f"/pupils/loans/{loan.pk}/return/", {"condition": "left ear crackles"})
    loan.refresh_from_db()
    headphones.refresh_from_db()
    assert loan.returned_at is not None and loan.condition_on_return == "left ear crackles"
    assert headphones.condition_note == "left ear crackles"


def test_an_item_out_cannot_be_lent_again(client, timetable, pupils, headphones):
    Loan.objects.create(item=headphones, pupil=pupils[0], out_at=timezone.now())
    client.post("/pupils/loans/", {"action": "lend", "lend-item": headphones.pk, "lend-pupil": pupils[1].pk})
    assert Loan.objects.count() == 1
    with pytest.raises(IntegrityError):
        Loan.objects.create(item=headphones, pupil=pupils[1], out_at=timezone.now())


def test_loans_page_lists_overdue_first(client, timetable, pupils):
    today = timezone.localdate()
    later = LoanItem.objects.create(name="Cable", identifier="A")
    overdue = LoanItem.objects.create(name="Ukulele", identifier="2")
    Loan.objects.create(item=later, pupil=pupils[0], out_at=timezone.now(), due=today + datetime.timedelta(days=3))
    Loan.objects.create(item=overdue, pupil=pupils[1], out_at=timezone.now(), due=today - datetime.timedelta(days=2))
    html = client.get("/pupils/loans/").content.decode()
    assert html.index("Ukulele 2") < html.index("Cable A") and "(overdue)" in html


def test_a_returned_item_can_go_out_again(client, timetable, pupils, headphones):
    Loan.objects.create(item=headphones, pupil=pupils[0], out_at=timezone.now(), returned_at=timezone.now())
    client.post("/pupils/loans/", {"action": "lend", "lend-item": headphones.pk, "lend-pupil": pupils[1].pk})
    assert Loan.objects.filter(returned_at__isnull=True).get().pupil == pupils[1]
