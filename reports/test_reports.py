import csv
import datetime
import io

import pytest

from assessment.models import Band, Component, Feedback, Strand
from notes.models import Note
from plans.models import LessonPlan, Scheme, Unit
from reports.compose import assemble, style_checks
from reports.models import ReportDraft, ReportSentence, ReportStyle, SummativeJudgement
from timetable.models import Pupil, Session

pytestmark = pytest.mark.django_db

D = datetime.date(2026, 10, 19)


@pytest.fixture
def frame(timetable, klass, room, pupils):
    unit = Unit.objects.create(scheme=Scheme.objects.create(name="Year 9"), name="Riffs")
    performing = Strand.objects.create(name="Performing", order=0)
    Component.objects.create(unit=unit, order=0, text="Plays a riff in time", strand=performing, next_step_default="x")
    secure = Band.objects.create(name="Secure", order=1)
    lesson = Session.objects.create(date=D, period="P1", klass=klass, room=room,
                                    lesson=LessonPlan.objects.create(unit=unit, order=1, objective="Riffs"))
    return {"unit": unit, "performing": performing, "secure": secure, "lesson": lesson}


def judge(pupil, frame):
    return SummativeJudgement.objects.create(pupil=pupil, unit=frame["unit"], strand=frame["performing"], band=frame["secure"])


# --- Drafting ---

def test_a_draft_uses_the_units_own_sentence_then_their_feedback(frame, pupils):
    ada = pupils[0]
    judge(ada, frame)
    ReportSentence.objects.create(band=frame["secure"], strand=frame["performing"], text="{name} performs securely.")
    ReportSentence.objects.create(band=frame["secure"], strand=frame["performing"], unit=frame["unit"],
                                  text="{name} keeps a riff steady with the band.")
    Feedback.objects.create(session=frame["lesson"], pupil=ada, develop="The fill rushes.", how="Count it out loud.")
    assert assemble(ada, [frame["unit"]]) == f"{ada.first_name} keeps a riff steady with the band. The fill rushes. Count it out loud."


def test_a_general_sentence_when_the_unit_has_none_and_nothing_without_a_judgement(frame, pupils):
    judge(pupils[0], frame)
    ReportSentence.objects.create(band=frame["secure"], strand=frame["performing"], text="{name} performs securely.")
    assert assemble(pupils[0], [frame["unit"]]) == f"{pupils[0].first_name} performs securely."
    assert assemble(pupils[1], [frame["unit"]]) == ""


def test_the_house_style_warns_and_never_blocks():
    style = ReportStyle(length_cap=20, third_person=True)
    warnings = style_checks("You played well and I enjoyed it, {name}.", style)
    assert any("over the limit of 20" in w for w in warnings)
    assert any("“I”" in w and "“You”" in w for w in warnings)
    assert any("{name}" in w for w in warnings)
    assert style_checks("Ada plays steadily.", style) == []
    assert style_checks("Your turn.", ReportStyle(third_person=False)) == []


# --- The class's reports page ---

def test_saving_and_redrafting_a_comment(client, frame, klass, pupils):
    ada = pupils[0]
    judge(ada, frame)
    ReportSentence.objects.create(band=frame["secure"], strand=frame["performing"], text="{name} performs securely.")
    url = f"/pupils/class/{klass.pk}/reports/"
    page = client.get(url).content.decode()
    assert f"{ada.first_name} performs securely." in page and "not saved yet" in page and "Download as CSV" in page
    response = client.post(url, {"pupil": ada.pk, "text": "  Ada plays with real control.  "})
    assert response.url == f"{url}#pupil-{ada.pk}"
    assert ReportDraft.objects.get(pupil=ada, klass=klass).text == "Ada plays with real control."
    client.post(url, {"pupil": ada.pk, "assemble": ""})
    assert ReportDraft.objects.get(pupil=ada).text == f"{ada.first_name} performs securely."


def test_the_page_shows_the_count_and_house_style_warnings(client, frame, klass, pupils):
    ReportStyle.objects.create(length_cap=10)
    ReportDraft.objects.create(pupil=pupils[0], klass=klass, text="You did well this term.")
    page = client.get(f"/pupils/class/{klass.pk}/reports/").content.decode()
    assert "23</span> of 10 characters" in page and "over the limit of 10" in page and "third person" in page


def test_a_pupil_from_another_class_is_refused(client, frame, klass):
    stranger = Pupil.objects.create(first_name="Zed", surname_initial="Q")
    assert client.post(f"/pupils/class/{klass.pk}/reports/", {"pupil": stranger.pk, "text": "x"}).status_code == 404


def test_the_csv_has_name_upn_bands_and_the_comment(client, frame, klass, pupils):
    ada = pupils[0]
    ada.upn = "A123456789012"
    ada.save()
    judge(ada, frame)
    ReportDraft.objects.create(pupil=ada, klass=klass, text="Ada plays with real control.")
    response = client.get(f"/pupils/class/{klass.pk}/reports.csv")
    body = response.content.decode("utf-8")
    assert body.startswith("﻿") and response["Content-Type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(body.lstrip("﻿"))))
    assert rows[0] == ["Name", "UPN", "Riffs: Performing", "Comment"]
    assert [str(ada), "A123456789012", "Secure", "Ada plays with real control."] in rows
    assert len(rows) == 1 + klass.pupils.count()


# --- Settings ---

def test_report_settings_hold_the_house_style_and_the_comment_bank(client, frame):
    data = {"style-length_cap": "600", "style-third_person": "on",
            "sentences-TOTAL_FORMS": "1", "sentences-INITIAL_FORMS": "0",
            "sentences-0-strand": frame["performing"].pk, "sentences-0-band": frame["secure"].pk, "sentences-0-unit": "",
            "sentences-0-text": "{name} performs securely."}
    client.post("/settings/reports/", data)
    assert ReportStyle.current().length_cap == 600
    assert ReportSentence.objects.get().unit is None


# --- Promote a note ---

def test_promoting_a_note_marks_it_and_sends_nothing(client, frame, pupils):
    note = Note.objects.create(session=frame["lesson"], pupil=pupils[0], text="Asked about the school band")
    page = client.get(f"/pupils/{pupils[0].pk}/").content.decode()
    assert "Copy for the school system" in page and 'data-text="Asked about the school band"' in page
    assert client.post(f"/pupils/notes/{note.pk}/promote/").url == f"/pupils/{pupils[0].pk}/#notes"
    note.refresh_from_db()
    first = note.promoted_to_mis_at
    assert first is not None
    client.post(f"/pupils/notes/{note.pk}/promote/")
    note.refresh_from_db()
    assert note.promoted_to_mis_at == first
    assert "promoted" in client.get(f"/pupils/{pupils[0].pk}/").content.decode()
