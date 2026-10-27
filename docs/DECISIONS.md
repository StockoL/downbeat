# Decisions

Choices the spec docs don't settle, made during the build. Newest at the bottom of each phase.

## Phase 1

**27 Oct 2026. Python 3.12, Django 5.2 LTS.** The project conventions name Python 3.12; the laptop also has 3.14, so the venv is pinned with `py -3.12`. Django 5.2 is the current 5.x LTS.

**27 Oct 2026. No login and no Django admin in Phase 1.** The app binds to localhost on the laptop and has one user, so `contrib.auth` and `contrib.admin` are left out. A login arrives in Phase 2, when Tailscale exposes the app to the iPad. All CRUD is on Downbeat's own pages, as the kickoff asks.

**27 Oct 2026. Theme generated from LooseLeaf's token compiler.** `tools/build-theme.mjs` sets the neutral ramp to zero chroma (greyscale chrome) and the action and accent hues to the same indigo (hue 270), so the interface has exactly one accent. One contrast pair falls short: link text on the dark surface is 4.15:1 against a 4.5 target, the same shortfall LooseLeaf's defaults have. Links are rare in the room view; revisit at the surface pass. A configurator export can replace the bundle at any time.

**27 Oct 2026. Navigation shows only areas that exist.** The desk navbar lists Today and Settings in Phase 1 (Plan once the seating editor exists). Sweep and Pupils appear when their phases build them, so no link leads to an empty page.

**27 Oct 2026. Checklist items and flag types are not in the Phase 1 first-run setup.** BUILD_ORDER's Phase 1 paragraph says the setup creates "the timetable, note types, checklist items and flag types", but ChecklistItem and FlagType are Phase 3 tables, the project conventions say not to scaffold later phases' models, and the kickoff says no flags. The setup wizard gains those steps in Phase 3.

**27 Oct 2026. First-run setup is one page, saved atomically.** The rule is "if no Timetable exists, redirect to setup". A multi-page wizard that saved the timetable first would release the redirect before note types and a room existed. One page with three sections (timetable and periods, note types, first room) saves everything in one transaction or nothing. Blank spare rows are ignored; at least one period and one note type are required. Placeholders show examples but no value is pre-filled.

**27 Oct 2026. The active timetable is the newest one.** The data model says "one active timetable; keep old ones for history" without an active field. `Timetable.active()` returns the most recently created, so no extra column is needed. A new timetable is made active by creating it.

**27 Oct 2026. Note type icon is a short text field.** An emoji or symbol the teacher types (★, ✎, ⚠). No icon library and no images; it renders as the seat badge.

**27 Oct 2026. Session carries a `period` label.** The data model gives Session a date and a nullable slot, but Today has to order sessions and know which one is live, and a one-off or moved session has no slot to read the period from. Session stores the period label, copied from its slot when generated and editable per day like the room. Times come from the active timetable's periods by label. Co-curricular sessions at lunch or after school use periods the teacher adds to the timetable ("Lunch", "After school").

**27 Oct 2026. Slots and sessions refer to periods by label.** Renaming a period in the timetable doesn't rename the slots that use it; the slots page lists them as using a period the timetable no longer has, with a link to fix each one. This keeps periods as plain JSON, as the data model has them.

**27 Oct 2026. Week A/B is chosen when generating.** The timetable doesn't record which calendar week is A. The generate form (and `manage.py generate_sessions --first-week`) asks which week the first date falls in, and alternates from that week's Monday. Holidays are handled by generating one half term at a time; generating again over the same dates never duplicates or overwrites a session.

**27 Oct 2026. Pasted class lists keep the surname initial only.** Pupils are quickest to add by pasting one per line on the class page. The last word on each line is taken as the surname and cut to its first letter, so "Aleya Khan" from a register is stored as "Aleya K" and the full surname is never saved. Lines of one word are skipped and listed back.

**27 Oct 2026. Deleting is guarded where history depends on it.** A class or room with sessions can't be deleted (the sessions will carry notes from step 7 onwards). Deleting a slot keeps its sessions, which become one-offs. Deleting a pupil removes them from every class.

**27 Oct 2026. Pupil keeps the recording permission fields now.** recording_permitted, exemplar_reuse_permitted and recordings_delete_by are fields on the Phase 1 Pupil table in the data model, so they are in the schema and the pupil form from the start, defaulting to off. Nothing uses them until Phase 5.

**27 Oct 2026. The room editor lives under Settings → Rooms.** UX.md's page inventory puts the room editor in Plan, but its Settings list also names rooms, and a room is drawn once and shared by every class. Configured-once work belongs in Settings. Per-class seating plans live under Plan.

**27 Oct 2026. Room stores the teacher position.** The data model has `near_teacher` on Seat but nowhere for the teacher-position marker the kickoff asks for. Room gains nullable `teacher_x` and `teacher_y`. An unplaced marker is drawn at the front centre. `near_teacher` stays a per-seat flag the teacher paints, not a distance computed from the marker, so the teacher decides what "near" means in each room.

**27 Oct 2026. Seats are 80 × 44 canvas units; new rooms default to 900 × 600.** Positions are stored in canvas units and the canvas scales to its container. At the room view's two-thirds of a laptop screen a 900-wide canvas renders near 1:1, so a seat stays close to the 44-point minimum tap size. A larger room can be given a bigger canvas, at the cost of smaller seats on screen. Dragging snaps to 10 units; arrow keys nudge a focused seat.

**27 Oct 2026. Zones are the five fixed choices from the data model.** Front, back, side, carpet, keyboard, or none. They are painted with a brush (choose a zone, tap seats) and show as text in the editor only; the room view doesn't display zones.

**27 Oct 2026. `DOWNBEAT_DB` overrides the database path.** Lets a throwaway database be used for browser checks without touching the real one.

**27 Oct 2026. Seating plans are edited under Plan; tap locks.** The Plan area in Phase 1 is one page of class cards, each listing its plans by room with a "new plan in…" picker. In the seating editor a pupil is dragged from the unseated list or from a seat; dropping on a seated pupil swaps them, or sends them back to the list if the dragged pupil wasn't seated. Tapping a seated pupil locks or unlocks them. A locked seat refuses to give up or take a pupil. The server re-renders the board after every change, so the page can't drift from the database.

**27 Oct 2026. The recycle bin is a drop target; undo lives in the browser session.** Dropping a pupil on the bin (or the unseated list) unseats them. Every move, swap, unseat and lock pushes a snapshot of the touched seats, before the change, onto an undo stack of ten per plan, held in the Django session rather than a new table. Undo is for a desk editing session; nothing in the data model needs it to survive a restart.

**27 Oct 2026. The no-plan fallback copies by zone, ordered from the teacher.** When a class has no plan for a room, a new one copies from the class's most recent plan in another room. Each seated pupil goes to a free seat of the same zone (no zone counts as a zone), and within a zone pupils keep their order outwards from the teacher marker (top to bottom if no marker), so front stays front even when the two rooms face different ways. Pupils with no matching seat are left unseated for the sweep. Locks aren't copied. No class plan elsewhere means a blank plan.

**27 Oct 2026. The plan in force is chosen by date.** `SeatingPlan.current` picks the class's plan for the room whose active_from is on or before the date and whose active_to is empty or on or after it, newest first. Phase 1 gives new plans active_from of today and no end; duplicate-to-reshuffle (Phase 3) will use the dates.

**27 Oct 2026. The canvas is capped at the screen height.** A canvas never grows taller than the viewport minus page chrome, so the whole room and the unseated list are on screen together while dragging.

**27 Oct 2026. Today redirects only when a session is live; `?list` always shows the list.** A session is live when now falls inside its period and it isn't cancelled. Outside lessons Today shows the day in period order (not alphabetical, so P10 follows P9), with the current or next one outlined. The room view's "Today" link adds `?list`, so the teacher can always reach the list mid-lesson without being bounced back.

**27 Oct 2026. Next session means the next one that isn't cancelled.** Later the same day first, then the following days (up to 60 days ahead). The N key and the "Next ›" button in the bar both go there. N lives in canvas.js's room-view mode, keeping to two hand-written JS modules, and is ignored while typing or while a sheet is open.

**27 Oct 2026. The room view's no-plan offer is one quiet line.** When the class has no plan for the session's room, a single muted line above the canvas offers "Seat by zone from M2" (or "Start a blank plan") as one tap that returns to the room view. It isn't red and doesn't count anything, and the room view works without it: unseated seats are simply empty.

**27 Oct 2026. The plan strip shows the period and its times until Phase 4.** There are no lesson plans yet, so the strip reads "P3 · 10:50–11:50". It becomes current-and-next activity, and the Log/Plan flip, when PlanActivity exists.

**27 Oct 2026. The picker button arrives with the picker (step 8).** The bottom bar in step 6 carries the Today link, session name and next session. No control appears before it does something.

**27 Oct 2026. Free text is a Note with no type.** Note.note_type is nullable; an empty type means free text, shown with ✎. The free-text form has a "Needs action" tick, the only choice in the whole note flow, because it is already the one form allowed.

**27 Oct 2026. Note leaves out the fields later phases need.** Group (Phase 3), voice_path and transcript (no voice notes yet) and promoted_to_mis_at (Phase 6) are added when their features are built, so the Phase 1 table holds nothing unused.

**27 Oct 2026. "Unread" counts a pupil's open actions.** The teacher writes every note, so nothing is literally unread. The counter on the note sheet's name and the dot on the seat show that pupil's actionable notes not yet done, from any lesson. Tapping the counter opens the inbox (all their notes, newest first); nothing else in the room shows past notes.

**27 Oct 2026. Seat badges are this lesson's notes.** A seat shows the icons of notes made for that pupil in this session, so the room shows what has happened this lesson and resets each lesson.

**27 Oct 2026. Notes go to a bin, with undo.** Each Log line has a one-tap remove, which sets a `deleted_at` (a field the data model doesn't list, added so removal is recoverable). An Undo button appears in the Log heading and reverses the last ten adds or removes this lesson, held in the browser session like seating undo. Removed notes vanish from every view.

**27 Oct 2026. Actions carry forward by query.** The Actions sheet lists open actionable notes from this session and from every earlier session with the same class (by date and period order). When a carried note is listed in a later session, `carried_to_session` is set to it, recording where it landed. Done is one tap. The bottom-bar counter is neutral: "Actions" alone when nothing is open, with a plain number otherwise.

**27 Oct 2026. Sessions and note types with notes are protected.** A session with notes can't be deleted (mark it cancelled instead), and a note type that has been used can't be deleted (rename it), so no note loses its lesson or its meaning.

**27 Oct 2026. Unseated pupils are still reachable in the room.** Pupils in the class without a seat in this plan show as a row of names under the room, with the same tap-for-the-sheet behaviour. Otherwise a blank plan or a new pupil would leave someone impossible to note.

**27 Oct 2026. SessionAttendance comes forward from Phase 3.** The picker has to skip absentees, which needs somewhere to record them. The data model's SessionAttendance (session, pupil, present) is added now, in the timetable app. It isn't a register: no row means present. Absence is a toggle beside "Spoken to" at the top of the note sheet (two taps, closes the sheet); an absent seat is faded and its name struck through.

**27 Oct 2026. Spoken to is a toggle.** One tap on "Spoken to" adds a row and closes the sheet; tapping it again on a dimmed pupil removes this lesson's rows, so a mistaken tap is undone the same way it was made.

**27 Oct 2026. "Missed last time" uses the class's previous lesson, and only if spoken-to was used in it.** The highlight (a thicker accent edge) goes to pupils with no spoken-to row in the class's last non-cancelled session. If that session has no spoken-to rows at all, nobody is highlighted, so a lesson where the feature wasn't used doesn't light up the whole class the next time.

**27 Oct 2026. The picker records on every draw and offers "is absent".** Each draw, including "tap to draw again", writes a spoken-to row, as the spec says. Because a name called to an empty chair would otherwise leave a wrong row, the picker shows "<name> is absent": one tap marks them absent, takes back that draw, and draws again. The default pool is present pupils not yet spoken to; when everyone has had a turn it draws from all present pupils. A toggle switches to the whole class. Unseated pupils are included, since the picker draws from the class, not the seats.

**27 Oct 2026. Seat states are data attributes on the seat's marks, styled with `:has()`.** Spoken to, absent and missed are flags on the marks element inside each seat, so the one out-of-band swap that already updates badges keeps every state current without re-rendering seats.

**27 Oct 2026. Projector view is black on white through the light system colours.** The page sets `color-scheme: light` and uses `Canvas`/`CanvasText`, so it stays high contrast with the laptop in dark mode and needs no raw colours. It shows seats, names and a "Front" marker, nothing else: no badges, counts, dimming, absence or highlights. It opens in a new window (to drag onto the projector's display), and its "Full screen" button is the only full-screen control in the app.

**27 Oct 2026. Cover PDF is drawn with reportlab.** A real A4 landscape PDF download, not a print stylesheet, so it can be emailed to cover. It carries the class and room as a title, the room outline, seats with names, the teacher position, and a "Not seated" line listing pupils without a seat. Nothing from notes, spoken-to or attendance. reportlab is pure Python with Windows wheels; it is the only new dependency in Phase 1.

**27 Oct 2026. The overflow menu sits at the right of the bottom bar.** A "⋯" button opens LooseLeaf's dropdown upwards with "Projector view" and "Cover PDF". Neither appears anywhere else on the room view.

**27 Oct 2026. Tests close the phase with an audit file.** Each step's tests went in with the step. `core/tests/test_audit.py` adds the cross-cutting checks: every mutating endpoint refuses GET and returns 404 for unknown rows; the error paths answer cleanly; and 25 seeded random runs of 60 moves, unseats, locks and undos each check that no seat holds two pupils, no pupil holds two seats, and a locked seat never changes under a move. Hypothesis isn't a dependency; seeded `random` keeps failures reproducible.

**27 Oct 2026. Demo data is a command against its own database.** `manage.py seed_demo` builds a disposable school for development: a two-week timetable, three rooms (rows, a keyboard room, the hall), five classes and a co-curricular choir, about 90 invented pupils (first name and initial, from a fixed seed so every run matches), sessions from last week to next, and past lessons with notes timed inside the lesson, open actions to carry, spoken-to rows and absences. One 8X lesson is moved to the hall, where 8X has no plan, to show the zone-copy offer. It is never run by a migration, refuses a database that already has data, and `--reset` refuses the default `db.sqlite3`, so it lives in `demo.sqlite3` via `DOWNBEAT_DB` and the real install still starts at first-run setup.

## Between phases: hardening

**27 Oct 2026. Phases are built in order without waiting for classroom use.** The build order gates each phase on a fortnight of real lessons. The teacher has chosen to have the app completed thoroughly before using it, so phases follow one another in BUILD_ORDER's order, each finished, tested and hardened before the next starts. The "Done when" tests remain the definition of done, checked against demo data until real use begins.

**27 Oct 2026. The data rules are implemented before Phase 2.** Settings → Data and three commands cover the Architecture section's promises. `manage.py backup` copies the live database with SQLite's online backup API, so it is consistent mid-write, converts the copy to a self-contained file, checks its integrity and keeps the newest 30 (`DOWNBEAT_BACKUP_DIR` and `DOWNBEAT_BACKUP_KEEP`; point the folder at OneDrive for the off-laptop copy). `tools/install-backup-task.ps1` registers a nightly Windows scheduled task that also runs at the next start-up if the laptop was off. `manage.py export_json` and "Download everything" give every row as JSON that `loaddata` reads back. "Delete everything" wipes every Downbeat row and browser session after the phrase "delete everything" is typed, and returns to first-run setup; backup files are separate and left for the teacher to remove. Restoring is copying a backup over `db.sqlite3` with the server stopped.

**27 Oct 2026. SQLite runs in WAL mode with IMMEDIATE transactions.** Readers no longer block on a writer, and overlapping writes wait up to 20 seconds rather than failing with "database is locked". This matters from Phase 2, when the iPad's queue syncs while the laptop is in use.

**27 Oct 2026. Per-install secrets and logs live in `local/`.** The secret key is generated on first start into `local/secret_key` (or taken from `DOWNBEAT_SECRET_KEY`), replacing the shared development default. Warnings and errors go to a rotating `local/logs/downbeat.log`. `local/` and `backups/` are ignored by git. DEBUG stays on while the app is served by `runserver` on localhost; Phase 2 replaces that with a proper server and turns it off.

**27 Oct 2026. A double tap never records twice.** Every HTMX button and form that posts disables itself while its request is in flight (`hx-disabled-elt`). An audit test fails if a template adds an `hx-post` without it.

**27 Oct 2026. Lint and CI.** Ruff checks the code (pyflakes, pycodestyle, import order, bugbear, pyupgrade, simplify; Django's `Meta` lists and the British typography in UI text are exempt). GitHub Actions checks out Downbeat and LooseLeaf side by side and runs ruff, `manage.py check`, a missing-migrations check and the tests on every push. Formatting is left as written rather than reformatting every file.

## Phase 2: iPad and offline

**27 Oct 2026. One teacher account, behind one gate.** Phase 2 makes the app reachable from the iPad, so it now needs a password. `django.contrib.auth` holds a single account. `core.middleware.GateMiddleware` applies three gates in order: no account yet → first-run setup (which now starts with "Your account"); signed out → login; signed in with no timetable → setup. An install from before sign-in existed (a timetable but no account) gets an account-only setup and keeps everything else. A signed-out HTMX request answers with `HX-Redirect`, so the whole page moves to the login rather than the form landing inside a sheet. The session lasts 120 days so the iPad never asks mid-lesson. Five wrong passwords from one address pause logins for five minutes. Passwords are at least ten characters. "Delete everything" keeps the account but signs every device out.

**27 Oct 2026. Served by waitress on localhost; Tailscale is the only way in.** `tools\serve.ps1` applies migrations, collects static files, runs Django's deploy checks and serves with waitress on 127.0.0.1, with debug off (debug is now opt-in through `DOWNBEAT_DEBUG=1`). Whitenoise serves static files. Nothing on the school network can reach the port; the iPad comes in through `tailscale serve`, which terminates HTTPS with Tailscale's real certificate for the laptop's `ts.net` name and forwards to localhost. `tools\tailscale-check.ps1` writes that name to `local\hosts.txt`, which turns on the allowed host, CSRF trusted origin, secure cookies, the forwarded-HTTPS header and HSTS. There is no HTTPS redirect, because the laptop itself uses plain HTTP on 127.0.0.1, which never leaves the machine. `tools\install-server-task.ps1` starts the server at Windows sign-in. `docs/TAILSCALE.md` is the step-by-step for the parts done on the devices.

**27 Oct 2026. `queue.js` is one file in two roles.** The project allows one hand-written JS module for the offline queue, "IndexedDB + service worker", but a service worker has to be fetched as its own script. `queue.js` checks where it is running: registered at `/sw.js` it is the service worker; loaded by a page it registers the worker and (from the queue step) holds captures. The server serves it at `/sw.js` with its cache version and precache list filled in. The version is a hash of the app-shell files, so any change to CSS or JS replaces the iPad's copy the next time it is online.

**27 Oct 2026. Caching: shell first, pages network-first with a four-second timeout.** Static files come from the cache. Pages and sheets go to the laptop first and are saved as they load; if the laptop doesn't answer within four seconds (school Wi-Fi) the saved copy is used, and a page never saved shows "Not reachable". Redirects aren't saved (a redirect usually means the session ended). Login, logout, the service worker and Settings → Data are never cached. Saved pages older than three days are dropped. Signing out empties every cache on that device, so the day's lessons can't be read offline by anyone else.

**27 Oct 2026. Icons are drawn by a script.** `tools/build_icons.py` draws a crotchet on the theme's accent from `tokens.resolved.json`, writing the PNGs with the standard library only (180 for iOS, 192, 512, and a 512 maskable with the note inside the safe zone). Rerun it after changing the theme.
