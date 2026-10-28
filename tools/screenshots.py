"""
Captures the screenshots in docs/screenshots/ from the demo school, for docs/SCREENSHOTS.md.

Rebuilds demo.sqlite3 with seed_demo --reset, serves it (and an empty install, for the first-run
setup) with waitress on localhost, drives a browser through the journeys with Playwright, then
stops both servers. Only invented demo pupils ever appear. Run from the repo root:

    .venv\\Scripts\\python -m pip install -r requirements-dev.txt
    .venv\\Scripts\\python tools\\screenshots.py                     # Microsoft Edge
    .venv\\Scripts\\python tools\\screenshots.py --channel chromium   # after `playwright install chromium`

The room view is captured with the browser's clock set 27 minutes into the demo's most recent
past lesson that has unit components, a hinge check and a seating plan, so times and the plan
strip read as they would mid-lesson.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
DEMO_DB = ROOT / "demo.sqlite3"
LAPTOP = {"width": 1440, "height": 900}
IPAD = {"width": 820, "height": 1180}  # iPad Air, portrait
MINUTES_IN = 27


def manage(env, *args):
    subprocess.run([sys.executable, "manage.py", *args], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)


def environment(db):
    env = {**os.environ, "DOWNBEAT_DB": str(db), "DJANGO_SETTINGS_MODULE": "downbeat.settings"}
    env.pop("DOWNBEAT_DEBUG", None)  # served as for real use, debug off
    return env


def serve(env, port):
    process = subprocess.Popen(
        [sys.executable, "-m", "waitress", f"--listen=127.0.0.1:{port}", "downbeat.wsgi:application"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/login/", timeout=1)
            return process
        except OSError:
            time.sleep(0.1)
    process.kill()
    raise SystemExit(f"The server on port {port} didn't start.")


def demo_ids():
    """Asks the demo database which lessons and pages to visit, in a child process."""
    script = r"""
import datetime, json
from django.db.models import Count
from django.utils import timezone
from assessment.models import Component, Feedback
from pupils.models import PupilFlag
from rooms.models import Room, SeatingPlan
from timetable.models import Class, Session, Timetable

today = timezone.localdate()
units = set(Component.objects.values_list("unit_id", flat=True))
# A lesson already under way 27 minutes in, so the faked browser clock is never in the future
# (sync holds a device's future clock to now, which would stamp captures with the real time).
lessons = Session.objects.filter(date__lte=today, klass__kind=Class.TIMETABLED, lesson__unit__in=units, lesson__checks__isnull=False).exclude(
    status=Session.CANCELLED)
def starts(s):
    return timezone.make_aware(datetime.datetime.combine(s.date, Timetable.active().period_times(s.period)[0]))
seated = [s for s in lessons if SeatingPlan.objects.filter(klass=s.klass, room=s.room).exists()
          and starts(s) + datetime.timedelta(minutes=30) < timezone.now()]
observe = max(seated, key=starts)
# Clear what the demo recorded in it, so the room reads as a lesson under way rather than history.
for related in (observe.notes, observe.spoken_to, observe.attendance, observe.checklist_ticks, observe.checks):
    related.all().delete()
observe.observations.filter(recording_path="").delete()  # recordings stay, for the pupil's timeline
start = Timetable.active().period_times(observe.period)[0]
past = Session.objects.filter(date__lt=today, lesson__isnull=False).annotate(n=Count("notes")).filter(n__gt=2).order_by("-date").first()
unit = Component.objects.order_by("unit__scheme__year_group", "unit__order").first().unit
print(json.dumps({
    "observe": str(observe.pk),
    "clock": datetime.datetime.combine(observe.date, start).isoformat(),
    "choir": str(Session.objects.filter(klass__kind=Class.CO_CURRICULAR).order_by("date").first().pk),
    "past": str(past.pk), "past_date": str(past.date),
    "plan": str(SeatingPlan.objects.annotate(n=Count("assignments")).order_by("-n").first().pk),
    "room": str(Room.objects.annotate(n=Count("seats")).order_by("-n").first().pk),
    "pupil": str(PupilFlag.objects.order_by("pupil__first_name").first().pupil_id),
    "klass": str(Class.objects.filter(kind=Class.TIMETABLED).order_by("name").first().pk),
    "unit": str(unit.pk),
    "lesson": str(unit.lessons.first().pk),
    "feedback_session": str(Feedback.objects.order_by("-session__date").first().session_id),
    "recorded": str(Feedback.objects.exclude(recording_path="").first().pupil_id),
    "nine_y": str(Class.objects.get(name="9Y Mu").pk),
    "codes_unit": str(Component.objects.filter(unit__feedback_codes__isnull=False).first().unit_id),
}))
"""
    env = environment(DEMO_DB)
    result = subprocess.run([sys.executable, "manage.py", "shell", "-c", script], cwd=ROOT, env=env,
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def capture(ids, base, fresh, channel):
    from playwright.sync_api import sync_playwright

    room = f"{base}/room/{ids['observe']}/"
    clock = datetime.datetime.fromisoformat(ids["clock"]) + datetime.timedelta(minutes=MINUTES_IN)
    errors = []

    def signed_in(browser, viewport, **options):
        ctx = browser.new_context(viewport=viewport, **options)
        ctx.clock.install(time=clock.isoformat())
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + "/login/")
        page.fill("[name=username]", "demo")
        page.fill("[name=password]", "demo-downbeat")
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_load_state()
        return ctx, page

    def shot(page, name, full=False):
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / f"{name}.png", full_page=full)
        print("  ", name)

    def visit(page, path, name, full=True):
        page.goto(base + path)
        page.wait_for_load_state("networkidle")
        shot(page, name, full)

    def open_room(page):
        page.goto(room)
        page.evaluate("navigator.serviceWorker.ready")
        page.reload()
        page.wait_for_load_state("networkidle")
        return page.locator("#sheet"), page.locator(".canvas .seat[data-pupil]")

    def synced(page):
        page.wait_for_function("document.querySelector('[data-sync-status]').textContent === ''", timeout=15000)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel)

        # An empty install, and the sign-in page.
        ctx = browser.new_context(viewport=LAPTOP)
        page = ctx.new_page()
        page.goto(fresh + "/")
        page.wait_for_load_state()
        shot(page, "01-first-run-setup", full=True)
        page.goto(base + "/login/")
        shot(page, "02-sign-in")
        ctx.close()

        # Laptop: a lesson with a few captures, then the desk pages.
        ctx, page = signed_in(browser, LAPTOP)
        visit(page, "/?list", "03-today", full=False)
        sheet, seats = open_room(page)

        def from_sheet(seat, selector):
            seats.nth(seat).click()
            sheet.wait_for(state="visible")
            page.locator(f"#sheet {selector}").first.click()

        for seat, nth in ((0, 0), (5, 0), (9, 1)):
            from_sheet(seat, f"[data-action=note] >> nth={nth}")
            sheet.wait_for(state="hidden")
        for seat, action in ((2, "spoken"), (3, "spoken"), (7, "absent")):
            from_sheet(seat, f"[data-action={action}]")
            sheet.wait_for(state="hidden")
        from_sheet(11, "[data-action=observe-sheet]")
        page.locator("#sheet [data-action=observe][data-state=partly]").first.click()
        page.keyboard.press("Escape")
        sheet.wait_for(state="hidden")
        synced(page)
        shot(page, "04-room-view-laptop")
        page.locator("[data-action=flip]").first.click()
        shot(page, "05-room-view-plan-panel")
        page.goto(room + "projector/")
        shot(page, "06-projector-view")

        visit(page, f"/plan/seating/{ids['plan']}/", "07-seating-editor", full=False)
        visit(page, f"/settings/rooms/{ids['room']}/", "08-room-editor", full=False)
        visit(page, "/plan/", "09-plan-classes")
        visit(page, f"/plan/classes/{ids['klass']}/", "10-class-lessons")
        visit(page, f"/plan/units/{ids['unit']}/assessment/", "11-unit-components")
        visit(page, f"/plan/lessons/{ids['lesson']}/", "12-lesson-editor")
        visit(page, f"/sweep/?date={ids['past_date']}", "13-sweep-day")
        visit(page, f"/sweep/{ids['past']}/", "14-session-sweep")
        visit(page, "/sweep/prep/", "15-prep")
        visit(page, f"/pupils/class/{ids['klass']}/", "16-class-pupils")
        visit(page, f"/pupils/{ids['pupil']}/", "17-pupil-page")
        visit(page, f"/pupils/class/{ids['klass']}/missing-out/", "18-missing-out")
        visit(page, "/pupils/loans/", "19-loans")
        visit(page, "/settings/", "20-settings")
        visit(page, "/settings/data/", "21-data")
        visit(page, f"/sweep/{ids['feedback_session']}/feedback/", "33-lesson-feedback")
        visit(page, f"/pupils/class/{ids['nine_y']}/components/", "34-class-components")
        visit(page, f"/pupils/class/{ids['nine_y']}/self-peer/", "35-self-and-peer")
        visit(page, f"/pupils/{ids['recorded']}/", "36-pupil-feedback-and-observations")
        visit(page, f"/plan/units/{ids['codes_unit']}/codes/", "37-feedback-codes-slide", full=False)
        visit(page, f"/pupils/class/{ids['nine_y']}/judgements/", "38-class-judgements")
        ctx.close()

        ctx, page = signed_in(browser, LAPTOP, color_scheme="dark")
        page.goto(room)
        page.wait_for_load_state("networkidle")
        shot(page, "22-room-view-dark")
        ctx.close()

        # iPad: the room in the hand.
        ctx, page = signed_in(browser, IPAD, has_touch=True)
        sheet, seats = open_room(page)
        shot(page, "23-ipad-room-view")

        seats.nth(14).click()
        sheet.wait_for(state="visible")
        shot(page, "24-ipad-note-sheet")
        page.keyboard.press("Escape")
        sheet.wait_for(state="hidden")

        box = seats.nth(15).bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.wait_for_timeout(700)  # longer than the long-press
        page.mouse.up()
        sheet.wait_for(state="visible")
        shot(page, "25-ipad-observation-sheet")
        page.locator("#sheet [data-action=observe][data-state=secure]").first.click()
        shot(page, "26-ipad-observation-next-step")
        page.keyboard.press("Escape")
        sheet.wait_for(state="hidden")

        page.locator("[data-action=hinge]").click()
        sheet.wait_for(state="visible")
        page.clock.run_for(47_000)  # the timer, as if the question has been up a while
        shot(page, "32-ipad-hinge-check")
        page.locator("#sheet [data-action=decide][data-decision=moved_on]").click()
        sheet.wait_for(state="hidden")

        for action, name in (("pick", "27-ipad-picker"), ("actions", "28-ipad-actions"), ("checklist", "29-ipad-checklist")):
            page.locator(f"[data-action={action}]").click()
            sheet.wait_for(state="visible")
            shot(page, name)
            page.keyboard.press("Escape")
            sheet.wait_for(state="hidden")

        synced(page)
        ctx.set_offline(True)
        for seat in (12, 13):
            from_sheet(seat, "[data-action=note]")
            sheet.wait_for(state="hidden")
        page.keyboard.press("l")  # opens the docked Log
        shot(page, "30-ipad-offline-log")
        ctx.set_offline(False)
        page.evaluate("window.downbeatQueue.flush()")
        synced(page)

        page.goto(f"{base}/room/{ids['choir']}/")
        page.wait_for_load_state("networkidle")
        page.locator("[data-action=register]").click()
        sheet.wait_for(state="visible")
        shot(page, "31-ipad-ensemble-register")
        ctx.close()
        browser.close()
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--channel", default="msedge", help="Playwright browser channel (msedge, chrome or chromium)")
    parser.add_argument("--port", type=int, default=8765, help="the demo's port; the empty install uses the next one")
    options = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    demo = environment(DEMO_DB)
    print("Rebuilding the demo school in demo.sqlite3")
    manage(demo, "migrate", "--noinput")
    manage(demo, "seed_demo", "--reset")
    manage(demo, "collectstatic", "--noinput")
    ids = demo_ids()

    with tempfile.TemporaryDirectory() as scratch:
        empty = environment(Path(scratch) / "empty.sqlite3")
        manage(empty, "migrate", "--noinput")
        servers = [serve(demo, options.port), serve(empty, options.port + 1)]
        try:
            print(f"Capturing into {OUT.relative_to(ROOT)}")
            errors = capture(ids, f"http://127.0.0.1:{options.port}", f"http://127.0.0.1:{options.port + 1}", options.channel)
        finally:
            for server in servers:
                server.terminate()
                server.wait()
    if errors:
        raise SystemExit("Page errors:\n" + "\n".join(errors))
    print("Done. The demo database now holds the captures made on the way.")


if __name__ == "__main__":
    main()
