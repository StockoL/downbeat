# Development

How to work on Downbeat's code. Read [BUILD_ORDER.md](BUILD_ORDER.md) and [UX.md](UX.md) first: they are the specification, and a change that conflicts with them should stop and be discussed rather than deviate.

## Setup

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
$env:DOWNBEAT_DEBUG = "1"
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py runserver
```

`runserver` doesn't apply migrations, so run `manage.py migrate` after pulling changes; until you do, every page says so. `tools\serve.ps1` migrates every time it starts. `requirements-dev.txt` adds ruff, Hypothesis and Playwright; pytest and pytest-django are in `requirements.txt`. LooseLeaf-UI must be checked out at `../looseleaf-ui`.

## Demo data

A disposable school for building and trying things out, kept in its own database so the real one stays empty:

```
$env:DOWNBEAT_DB = "demo.sqlite3"
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_demo
.venv\Scripts\python manage.py runserver
```

Sign in as `demo` / `demo-downbeat`. The school has a two-week timetable, three rooms (rows, a keyboard room, the hall), five classes and a choir, about 90 invented pupils from a fixed seed, sessions from last week to next with notes, actions, spoken-to rows and absences, plus flags, relationships, groups, rotations, loans, schemes of work and unit components.

`seed_demo --reset` wipes and rebuilds it. It refuses to run on `db.sqlite3`, and refuses a database that already has data without `--reset`. Close the terminal, or `Remove-Item Env:DOWNBEAT_DB`, to go back to the real database.

## Project layout

```
downbeat/     settings, root URLs
core/         Base model, the gate, first-run setup, sign-in, Settings → Data, the PWA endpoints
timetable/    Timetable, Slot, Session, Class, Pupil, attendance, rotations; Today and the room view
rooms/        Room, Seat, SeatingPlan, SeatAssignment; adjacency, the solver, the cover PDF
notes/        NoteType, Note, SpokenTo, goals, checklist; sync and lesson state
pupils/       flags, relationships, groups, loans; the Pupils area
plans/        schemes, units, lessons, activities, resources; Sweep and Prep
assessment/   strands, bands, components, feedback codes, observations; criteria files
templates/    one base, two layouts (room and desk), partials for HTMX
static/       css/downbeat.css, js/canvas.js, js/queue.js, theme/, icons/
tools/        serve, scheduled tasks, Tailscale check, theme and icon builders, screenshots
docs/         the documentation
```

Apps are created when their phase starts; no later phase's models are scaffolded early. [ARCHITECTURE.md](ARCHITECTURE.md) explains how the parts fit together.

## Conventions

**Rules that override any task.** The sixteen rules at the end of [BUILD_ORDER.md](BUILD_ORDER.md#rules-the-build-must-not-break) hold everywhere. The ones most often in play while coding:

- In-lesson capture is at most two taps and never opens a form.
- The room view tolerates a lesson with zero input: no nags, no empty-state prompts, no red counts.
- Bands are entered by the teacher, never computed. No averages, flight paths or target grades.
- Flags render as colour only. The projector view and cover PDF show names and nothing else.
- Pupil names are first name plus surname initial. No photographs, full surnames or dates of birth.
- Nothing writes to the school's systems. No personal values are seeded in migrations.
- Before adding anything to the room view, name what it displaces. If nothing, it belongs on a desk page.

**Models.** Every model inherits `core.models.Base`: a UUID primary key, `created_at` and `updated_at`, so rows made offline merge without renumbering. When unsure whether a field belongs, check the data model tables in BUILD_ORDER, which are deliberate about what they leave out. A new model must be added to `APP_MODELS` and `EXPORT_APPS` in `core/data.py`; a test fails otherwise.

**Stack.** Django 5.2, SQLite, HTMX. No React, no Django REST Framework; the few JSON endpoints are plain views. Two hand-written JavaScript modules only: `static/js/canvas.js` (the seating canvas and the room view) and `static/js/queue.js` (the service worker and the IndexedDB queue). Text from the database is only ever set with `textContent`.

**HTMX.** Every `hx-post` carries `hx-disabled-elt` so a double tap never records twice; an audit test enforces it.

**CSS.** Use LooseLeaf-UI's compositions (`.sidebar`, `.grid`, `.cluster`, `.flow`, `.switcher`, `.reel`) and blocks (`.button`, `.card`, `.badge`, `.modal`, `.offcanvas`, `.field`, `.table`) before writing any CSS. Downbeat's own rules go in `static/css/downbeat.css` only: semantic tokens, no raw hex, no `!important`, container queries rather than viewport queries, `dvh` rather than `vh`, hover only inside `@media (hover: hover)`. The flag palette (`--flag-1` to `--flag-8`) and group tints (`--group-1` to `--group-6`) are reserved Tier 3 variables used nowhere else.

**Writing.** British spelling in UI text and comments. UI text is plain and neutral: information, never warnings about things the teacher didn't do.

**Decisions.** Any choice the spec doesn't settle gets a dated entry in [DECISIONS.md](DECISIONS.md) with its reasoning, under the phase it belongs to.

## Commits

Small commits with plain messages, one per build step, each with its tests. Never commit the SQLite databases, `local/`, `backups/`, media or anything under `recordings/` (all ignored). Lint and tests must pass before a push; CI runs them again. See [TESTING.md](TESTING.md).

## Theme and icons

The theme bundle in `static/theme/` is built from LooseLeaf's tokens: greyscale chrome and one indigo accent.

```
node tools/build-theme.mjs ../looseleaf-ui static/theme
.venv\Scripts\python tools/build_icons.py
```

A bundle exported from the LooseLeaf configurator can replace it. Rebuild the icons after changing the theme, since they take the accent colour from `tokens.resolved.json`.

## Screenshots

`docs/screenshots/` and [SCREENSHOTS.md](SCREENSHOTS.md) show the journeys and key features. After a change that alters a screen, capture them again:

```
.venv\Scripts\python tools\screenshots.py
```

The tool rebuilds `demo.sqlite3` with `seed_demo --reset`, then serves it alongside an empty install (for the first-run setup) with waitress on ports 8765 and 8766. It drives Microsoft Edge through each journey with Playwright and stops both servers when it finishes. The browser's clock is set 27 minutes into the demo's first lesson with unit components, so the room view reads as it would mid-lesson. It fails if any page raises a JavaScript error. Use `--channel chromium` (after `.venv\Scripts\playwright install chromium`) on a machine without Edge, and `--port` if 8765 is taken.

Only invented demo pupils appear in the screenshots, and they never come from `db.sqlite3`. When a new screen is built, add a capture to the tool and a section to SCREENSHOTS.md in the same commit.

## Gotchas

- **Restart the server after editing static files** when serving through `serve.ps1`: whitenoise caches file sizes at start-up and will serve a truncated file otherwise.
- **The service worker caches the shell.** Its cache version is a hash of the shell files, so a change reaches the iPad on its next online load; in a desktop browser, a hard reload or "Update on reload" in the developer tools avoids confusion.
- **`hidden` inside compositions.** LooseLeaf compositions set `display`, which beats the `hidden` attribute; `downbeat.css` restores it inside the room view's panel and sheets. Keep that in mind when hiding something elsewhere.
