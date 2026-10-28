# Architecture

How Downbeat's parts fit together. The *what* and *why* are in [BUILD_ORDER.md](BUILD_ORDER.md); the dated reasoning behind each choice is in [DECISIONS.md](DECISIONS.md).

## Shape

```
            iPad (in the room)                               Laptop (at the desk)
   +----------------------------------+            +-------------------------------------+
   | Safari, installed PWA            |            | Browser -> http://127.0.0.1:8000    |
   |                                  |            |                                     |
   |  room view (canvas.js)           |   HTTPS    |  tailscale serve (ts.net cert)      |
   |   draws lesson state + pending   | ---------> |        |                            |
   |  queue.js                        |  Tailscale |        v                            |
   |   IndexedDB: captures waiting    |            |  waitress -> Django -> SQLite (WAL) |
   |   service worker: shell + pages  |            |              ^                      |
   +----------------------------------+            |  nightly backup -> OneDrive folder  |
                                                    +-------------------------------------+
```

The laptop's SQLite database is the only source of truth. The iPad holds a cache of pages and lesson state, and a queue of captures; nothing on it is authoritative. One responsive front end serves both devices; the layout changes with the width of the room view's container, never with the device.

## Django apps

| App | Owns | Notable modules |
| --- | --- | --- |
| `core` | `Base` (UUID key, timestamps), the gate, first-run setup, sign-in, Settings → Data, PWA endpoints | `middleware.py`, `data.py`, `pwa.py`, `auth_views.py` |
| `timetable` | Timetable, Slot, Session, Class, Pupil, SessionAttendance, Rotation, PupilRotation; Today and the room view | `services.py` (sessions, live and next), `rotations.py`, `lesson_views.py` |
| `rooms` | Room, Seat, SeatingPlan, SeatAssignment | `seating.py`, `adjacency.py`, `solver.py`, `cover.py` |
| `notes` | NoteType, Note, SpokenTo, Goal, ChecklistItem, ChecklistTick | `sync.py`, `state.py`, `goals.py` |
| `pupils` | FlagType, PupilFlag, Relationship, Group, GroupMember, LoanItem, Loan; the Pupils area | `missing_out.py` |
| `plans` | Scheme, Unit, LessonPlan, PlanActivity, Resource, ActivityStatus, SessionReflection, PrepItem; Sweep and Prep | `services.py`, `sweep.py`, `prep.py` |
| `assessment` | Strand, Band, Component, FeedbackCode, Observation, Check, CheckResponse | `criteria.py`, `hinge.py`, `forms.py` |

Areas map to tempos, not tables: Today (catch), Sweep and Prep (sweep), Plan (plan), Pupils (any time) and Settings.

## The gate

`core.middleware.GateMiddleware` runs on every request and applies three gates in order:

1. No account exists → first-run setup.
2. Signed out → login. An HTMX request gets an `HX-Redirect` header so the whole page moves; `/sync/` and lesson state get a 401 JSON answer so the device keeps its queue.
3. Signed in but no timetable → setup.

Login, the PWA files and static files pass through. Five wrong passwords from one address pause logins for five minutes.

## The room view

The room view is one Django page that embeds the lesson as JSON (`notes/state.py`, `lesson_state`): seats, pupils, notes, spoken-to, attendance, actions, goals, checklist, plan activities with the period's start and end, carried activities, components, observations, the hinge check and its decisions. Sheets (note, observation, hinge, free text, picker, actions, checklist, register) are `<template>` elements rendered by Django and filled by `canvas.js`.

`canvas.js` draws everything from that state, then replays this device's pending operations on top through `applyOp`, the same rules the server applies. So a capture appears at once, online or not, and the screen never waits on the network.

## Captures, the queue and sync

Every capture in the room is an **operation** with an id made on the device:

| Operation | What it does |
| --- | --- |
| `note.add`, `note.remove`, `note.restore` | A note for a pupil or group; remove and restore go via a bin |
| `action.done` | Ticks an actionable note done |
| `spoken.add`, `spoken.remove`, `spoken.clear` | Spoken to, from a tap or the picker |
| `attendance.set` | Absent or present |
| `checklist.tick`, `checklist.untick` | This lesson's checklist |
| `observation.add`, `observation.update`, `observation.remove` | An observation against a component, its next step |
| `check.decide`, `check.clear` | The hinge decision for the class; the first copies the planned question into the session |

There is one path whether the laptop is in reach or not:

1. `queue.js` (`window.downbeatQueue.submit`) saves the operation to IndexedDB, and the room view draws it.
2. The queue posts pending operations to `/sync/` whenever it can.
3. `notes/sync.py` applies each one idempotently, inside a transaction:
   - Adds carry their own UUIDs, so a resend creates nothing new.
   - Removes, restores and attendance compare the operation's time with the row's `updated_at` (last write wins).
   - Rows take the time they were caught, not sent; a device clock more than five minutes ahead is held to now.
   - Operations that can never apply (a deleted lesson, an observation with no next step) are rejected and dropped; anything else waits.
4. After a sync the room view fetches fresh state and stops replaying an operation only once the state includes it.

Seating edits are not queued: they happen at the desk, online.

## The service worker

`queue.js` is one file in two roles. Served at `/sw.js` (by `core/pwa.py`, with its cache version and precache list injected) it is the service worker; loaded by a page it is the queue. The cache version is a hash of the app shell, so any CSS or JS change replaces the iPad's copy on its next online load.

- Static files: cache first.
- Pages and lesson state: network first with a four-second timeout, then the saved copy, then a "Not reachable" page. Redirects are not saved. Saved pages older than three days are dropped.
- Never cached: login, logout, the service worker itself and Settings → Data. Signing out empties every cache.

## Seating

- **Adjacency** (`rooms/adjacency.py`): two seats are neighbours when their centres fall inside an ellipse about two seat widths across and under two seat depths front to back. One definition, used by the editor's validation lines and the solver.
- **Solver** (`rooms/solver.py`): a pure function over seat ids, pupil ids and constraints. Hard rules (locked seats keep their pupil; keep-apart pairs are never neighbours) are never broken: if no arrangement satisfies them it raises `NoArrangement` rather than returning a compromise. Soft goals are scored (flag placement rules 10 points, pair-well pairs 3). Forty randomised depth-first searches with backtracking, hardest pupils first, best score kept.
- **Zone copy** (`rooms/seating.py`): when a class is taught in a room it has no plan for, a plan is offered that copies seats zone by zone from its plan elsewhere, ordered outwards from the teacher position, so front stays front.

## Data safety

| Promise | Where it is kept |
| --- | --- |
| Local only | waitress binds to 127.0.0.1; Tailscale is the only way in |
| Names are first name and initial | `Pupil` has no surname field; pasted class lists are cut to the initial |
| Flags are colour only | Flag labels are rendered on the pupil page only; lesson state, projector view and cover PDF carry no flags |
| Bands never computed | No field or function derives a band, average or percentage |
| Whole-class checks store the decision | Sync has no operation for a pupil's answer; answers are entered in the sweep only when the unit opts in, and kept only with a decision |
| Observations carry a next step | Sheet attaches the default, sync rejects without one, and a database check constraint refuses a row with neither a next step nor a recording |
| Nightly backup | `core/data.py` `backup`, scheduled by `tools/install-backup-task.ps1` |
| Export and delete-all | `core/data.py` `export_json` and `delete_all`, over `APP_MODELS`; a test fails if a model is missing |
| Concurrent writes | SQLite WAL mode, IMMEDIATE transactions, 20-second busy timeout |

## Front end

- **HTMX** for desk pages; every `hx-post` disables its control while in flight.
- **LooseLeaf-UI** (CUBE CSS) for compositions, blocks and the theme; `static/css/downbeat.css` holds Downbeat's own rules, including the reserved flag and group palettes.
- **Two layouts**: `layouts/room.html` and `layouts/desk.html` over one base. In the room view the panel is a side column at 76rem of container width and above, and a docked sheet with a handle below it.
