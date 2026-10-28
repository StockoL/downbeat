# Testing

How Downbeat is tested, how to run the tests, and what each part of the suite covers.

## Running the tests

```
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
.venv\Scripts\ruff check .
```

The suite runs in about ten seconds: 387 tests pass and 4 are skipped (see [Skipped tests](#skipped-tests)). `pytest -q path/to/file.py -k name` runs one file or test.

GitHub Actions (`.github/workflows/tests.yml`) runs on every push and pull request. It checks out Downbeat and LooseLeaf-UI side by side, then runs:

1. `ruff check .`
2. `manage.py check` and `manage.py makemigrations --check --dry-run` (fails if a model change has no migration)
3. `pytest -q`

## Strategy

The test effort follows the risks of this particular app, which are not the usual ones for a web app:

| Risk | What guards it |
| --- | --- |
| A capture made offline is lost, duplicated or applied out of order | Sync tests send operations twice, out of order, from a fast clock and after sign-out |
| A rule the spec forbids creeps in (a nag, a flag label on a seat, a computed figure) | Tests that assert something is *absent*: no nag in an empty lesson, nothing but names on the projector view and cover PDF, no next-step-less observation, no pupil's hinge answer unless the unit opts in |
| The seating shuffle breaks a hard rule | Property-based tests over generated rooms, classes and constraints |
| A mutating endpoint is reachable by GET, or crashes on an unknown id | An audit test parametrised over every mutating URL |
| Data the teacher can't get back out, or can't delete | Export and delete-all are checked against every model in every app |
| A double tap records twice | An audit test fails if any `hx-post` lacks `hx-disabled-elt` |

Conventions:

- **pytest-django** throughout. Every view that changes data has a test.
- **Tests are named as sentences** about behaviour (`test_rule_four_no_next_step_no_observation`, `test_spoken_clear_spares_a_later_tap`), so the suite reads as a specification.
- **Each build step's tests go in with the step**, in the same commit.
- **Fixtures** live in the root `conftest.py`: `teacher`, `client` (signed in), `anon_client`, `timetable` (an installed app, so the first-run gate stays out of the way), `room`, `klass` and `pupils`. Password hashing uses MD5 in tests for speed.

## Property-based tests

`rooms/test_solver.py` uses Hypothesis to generate rooms (grids of seats), classes, keep-apart and pair-well relationships, locks and flag rules, then checks every plan the solver returns:

- locked seats never move;
- keep-apart pairs are never neighbours;
- nobody is seated twice and everyone who fits is seated;
- with no hard constraints the solver never refuses.

`core/tests/test_audit.py` adds 25 seeded random runs of 60 moves, unseats, locks and undos in the seating editor, checking that no seat ever holds two pupils, no pupil two seats, and a locked seat never changes. Seeded `random` keeps a failure reproducible.

## What each file covers

| File | Tests | Covers |
| --- | ---: | --- |
| `core/tests/test_setup.py` | 10 | First-run setup: nothing seeded, saved atomically or not at all, every page redirects until done, closed once done, flag types |
| `core/tests/test_auth.py` | 12 | The gate's three stages, the account section and account-only setup, login throttling, safe `next`, HTMX redirects |
| `core/tests/test_data.py` | 11 | Backup, JSON export round trip, delete-all; every model is in both lists |
| `core/tests/test_pwa.py` | 6 | Manifest, versioned service worker, every precached file exists, offline page holds no pupil data, sign-out clears saved pages |
| `core/tests/test_audit.py` | 73 | Every mutating endpoint refuses GET and 404s on unknown rows; seeded random seating runs; `hx-disabled-elt` everywhere |
| `core/tests/test_seed_demo.py` | 4 | The demo builds, and refuses the real database |
| `core/tests/test_scaffold.py` | 2 | The abstract Base model (UUID, timestamps) and the desk layout |
| `timetable/tests/test_generate.py` | 5 | Session generation, week A/B, no duplicates on re-running |
| `timetable/tests/test_views.py` | 29 | Timetable, slots, classes, pupils (initial only), one-off sessions and room changes, deletion guards |
| `timetable/tests/test_lesson.py` | 12 | Today lands on the live session, next session, the room view and the no-plan offer |
| `timetable/tests/test_projector_cover.py` | 4 | Projector view and cover PDF carry names and nothing else |
| `timetable/tests/test_rotations.py` | 12 | Generating and pasting rotations, who is out this period |
| `rooms/tests.py` | 14 | Room editor: seats, zones, teacher position |
| `rooms/test_seating.py` | 25 | Move, swap, lock, bin, undo, zone copy, plan by date, shuffle and duplicate |
| `rooms/test_adjacency.py` | 6 | The neighbour ellipse |
| `rooms/test_solver.py` | 6 | Solver properties (Hypothesis) and the three-keep-apart case |
| `notes/tests.py` | 20 | Sync operations, idempotency, last write wins, clock skew, rejection; lesson state; zero-input room view; inbox; shortcuts |
| `notes/test_goals.py` | 12 | Goals count lessons, weekly windows, checklist ticks through the queue, the ensemble register |
| `pupils/tests.py` | 19 | Flags are colour only everywhere but the pupil page; relationships stored once; validation lines in the editor |
| `pupils/test_groups.py` | 10 | Groups, tints, ending, group notes |
| `pupils/test_loans.py` | 5 | Lending, returning, one open loan per item |
| `pupils/test_missing_out.py` | 4 | Fewest house points and turns first, the half-term window |
| `plans/tests.py` | 10 | Schemes, units, lessons, activities, resources, duplicate unit, fill in order |
| `plans/test_sweep.py` | 10 | Activity statuses, carry-forward, binning, group attribution, reflection and spawned goals |
| `plans/test_prep.py` | 6 | Prep generated from resources and actions, ticks kept, manual items |
| `assessment/tests.py` | 9 | Strands and bands, components and codes, criteria file round trip and refusal, duplicating a unit |
| `assessment/test_observations.py` | 7 | Observations through sync, rule 4 in sync and in the database, backwards states, sweep bin |
| `assessment/test_feedback.py` | 17 | Feedback for a pupil or a group, written from a lesson or a pupil's page, its three parts, recordings only with permission (every member for a group), the m:ss moment, codes as a slide with no pupil in it, the class-by-component view (latest state, by assessor, nothing added up), self and peer in one go with the next step attached |
| `assessment/test_recordings.py` | 13 | The exemplar bank and its permission, recordings on the pupil's timeline in order, the link-or-path rule, removing references past the delete-by date or without permission (and from the Data page and the command), and the per-pupil export following every link to a pupil |
| `assessment/test_checks.py` | 18 | Hinge checks: misconception-tagged wrong answers, the bank and duplication, planned-or-asked constraint, decisions through sync (minutes in, idempotent, last write wins, two devices, taking back), the greyed button, the sweep's judgement, pupils' answers opt-in and only with a decision (rule 3) |

## Traceability to the "Done when" tests

Each phase in [BUILD_ORDER.md](BUILD_ORDER.md#build-order) ends with a "Done when" test meant for a real lesson. Until the app is in classroom use they are checked against the demo school, and the automated tests below hold the mechanics in place.

| Phase | Done when | Automated cover | Checked by hand |
| --- | --- | --- | --- |
| 1 | Two weeks of lessons without the paper plan | `test_lesson.py`, `notes/tests.py`, `test_seating.py`, `test_projector_cover.py` | Every Phase 1 journey in Edge on the demo school |
| 2 | A lesson logged on the iPad with Wi-Fi off appears on the laptop that evening | `notes/tests.py` (sync), `test_pwa.py`, `test_auth.py` | Edge in offline mode at iPad size; **outstanding on a real iPad** |
| 3 | A plan for a class with three keep-aparts can be generated; the house-point tally is visible by Wednesday | `test_solver.py` (three keep-aparts), `test_goals.py` | Shuffle and bar counters in Edge |
| 4 | An unfinished activity from Tuesday is carried to the next Tuesday; Prep lists tomorrow's printing unprompted | `test_sweep.py`, `test_prep.py` | Sweep and Prep in Edge |
| 5 | A unit taught end to end with components declared; the sweep under three minutes | `assessment/` | Observation and hinge sheets in Edge at iPad size; every desk page through the screenshot tool |

## Browser checks

Behaviour that only exists in the browser (the canvas, the queue, the service worker, gestures, layout breakpoints) is checked in Microsoft Edge against `tools/serve.ps1` on the demo database, driven by Playwright. Step-specific check scripts are kept outside the repository, and `tools/screenshots.py` walks every built journey end to end, failing on any JavaScript error. Each step's check is recorded in [DEVLOG.md](DEVLOG.md). The standing list:

- **Layout**: the room view at laptop width (side panel) and at iPad portrait and landscape (docked sheet with handle); nothing tappable under 44 points; dark mode.
- **Offline**: with the network cut, a note, spoken-to, absence, picker draw, checklist tick and observation all draw at once and say "saved on this device"; after reconnecting they reach the laptop's database exactly once.
- **Gestures**: tap a seat for the note sheet; long-press for the observation sheet; a moved finger cancels the long-press.
- **Keyboard**: N, P, A, U, L, ? and the sheet keys 1–9, S, X, F, O; none fire while typing.
- **Zero input**: a lesson with no captures shows no prompts, counts or colour.

Serve a fresh copy after any static change (whitenoise caches file sizes at start-up).

[SCREENSHOTS.md](SCREENSHOTS.md) is the latest visual record of these checks, regenerated by `tools/screenshots.py` (see [DEVELOPMENT.md](DEVELOPMENT.md#screenshots)).

### On the real iPad

Still to do, by the teacher, once Tailscale is set up ([TAILSCALE.md](TAILSCALE.md)):

1. Add to Home Screen from the `ts.net` address; it opens full screen with the Downbeat icon.
2. Open today's lesson, then turn Wi-Fi off.
3. Make notes, a picker draw, an absence and an observation; the bar shows them as saved on the device.
4. Close the app, reopen it offline; the lesson and the captures are still there.
5. Turn Wi-Fi on; the bar clears, and the laptop shows every capture once, at the time it was made.

## Skipped tests

The three skips are parametrised cases of the audit's "404 on unknown rows" check for endpoints that take their row ids from the posted form rather than the URL; the check doesn't apply to them, and each is covered by its own view test.
