# Development log

What was built in each step, how it was checked, and what went wrong along the way. The reasoning behind each choice is in [DECISIONS.md](DECISIONS.md); this log is the story of the build. Newest phase at the bottom.

Each step ends with ruff and the full test suite passing locally and in CI, and with a browser check in Edge against the demo school ([TESTING.md](TESTING.md#browser-checks)).

## Phase 1: the room

*Goal: replace the paper seating plan and mark-book shorthand on the laptop.*

| Commit | Step |
| --- | --- |
| `dabbd67` | Django project, the abstract `Base` model (UUID key, timestamps), base template with room and desk layouts, LooseLeaf theme |
| `6f646c6` | First-run setup: timetable and periods, note types and a first room on one page, saved atomically |
| `07f03a5` | Timetable, slots, sessions, classes and pupils, with Settings pages and session generation for week A/B |
| `c1d738b` | Room editor: free-placed seats on a canvas, zone painting, the teacher position |
| `27e5ba9` | Seating plans: drag, swap, lock, recycle bin, undo, and the zone-copy fallback for a room the class has no plan for |
| `01c9c4b` | Today, which lands on the live session, and the room view with the next-session key and the no-plan offer |
| `7982a0c` | The note sheet, the Log, seat badges, the inbox, the Actions sheet and Settings for note types |
| `700ca1a` | Spoken-to, absence, next-lesson highlights, and the random picker that skips absentees |
| `789621d` | Projector-safe view and cover PDF, behind the room view's overflow menu |
| `9f8b253` | Audit tests: every mutating endpoint, and seeded random runs of seating edits |
| `709a985` | `seed_demo`: a disposable demo school in its own database |

**Went wrong, put right.**
- The first theme came out tinted indigo throughout: a bulk edit to set the accent hue also changed the neutral ramp. `tools/build-theme.mjs` now sets the neutral ramp to zero chroma explicitly.
- The first-run setup was planned as a multi-page wizard, but saving the timetable first would have released the "no timetable → setup" redirect before note types and a room existed. It became one page saved in one transaction.

## Between phases: hardening

*Goal, from the teacher: "Anything that makes the build more logical, safer, and stable."* From here, phases follow one another without waiting for classroom use; each "Done when" is checked against the demo school.

| Commit | Step |
| --- | --- |
| `7323cf2` | Backups through SQLite's backup API with integrity checks, JSON export, delete-all behind a typed phrase, WAL mode with IMMEDIATE transactions, a per-install secret key, a double-tap guard on every HTMX post, ruff and GitHub Actions CI |

## Phase 2: iPad and offline

*Goal: log a lesson on the iPad with the Wi-Fi off and see it on the laptop that evening.*

| Commit | Step |
| --- | --- |
| `adc9713` | Sign-in with the three-stage gate, waitress on localhost, Tailscale for the iPad, and `docs/TAILSCALE.md` |
| `578b782` | The PWA shell: manifest, icons drawn by a script, service worker and offline page |
| `f866d19` | Every room-view capture as an operation in an IndexedDB queue, synced idempotently to `/sync/`; the room view redrawn from lesson state |
| `4ddf44d` | The panel docked as a sheet below desk width, and laptop keyboard shortcuts |

**Went wrong, put right.**
- An install that had a timetable from before sign-in existed but no account looped between setup and login. The gate now offers an account-only setup to such an install.
- After editing JavaScript, the browser received a truncated `canvas.js`: whitenoise caches file sizes when the server starts. The server is now restarted after every static change, and the note is in [DEVELOPMENT.md](DEVELOPMENT.md#gotchas).
- A 1024px breakpoint, as UX.md suggested, would have given a landscape iPad (1180px) the laptop's side panel, which UX.md also rules out. The breakpoint became 76rem on the room's container.

**Outstanding:** the end-to-end check on a real iPad ([TESTING.md](TESTING.md#on-the-real-ipad)).

## Phase 3: flags, relationships, groups, goals

*Goal: generate a plan for a class with three keep-aparts; see the house-point tally by Wednesday.*

| Commit | Step |
| --- | --- |
| `f0e0bf4` | Flags: eight reserved colours on the seat's edge, labels on the pupil page only |
| `1d08a91` | Relationships, and live validation lines in the seating editor |
| `f947fb1` | The seating shuffle (a randomised depth-first solver) with Hypothesis property tests, and duplicate-to-reshuffle |
| `3585f61` | Groups: tints, management under Plan, group notes |
| `3aa8af2` | Weekly goals and the lesson checklist as bar counters, offline through the queue |
| `7082ba3` | The ensemble register for co-curricular sessions |
| `cab4cad` | Instrumental rotations: grey seats and Today counts for pupils out at lessons |
| `7bb69a9` | The equipment loan log |
| `e040043` | The "missing out" check per class |

**Went wrong, put right.**
- A single adjacency radius couldn't fit real rooms: any circle wide enough to reach the next desk along also reached two rows back, so the solver refused plans a teacher would accept. Adjacency became an ellipse, wider than it is deep, defined once in `rooms/adjacency.py`.

## Phase 4: plans, curriculum skeleton, prep, sweep

*Goal: an unfinished Tuesday activity appears on the following Tuesday's plan; Prep lists tomorrow's printing unprompted.*

| Commit | Step |
| --- | --- |
| `628b442` | Schemes, units, lessons with activities and resources; sessions point at lessons; fill a class's sessions from a unit |
| `9ee8d5b` | The Plan side of the room view's panel, with the strip as the flip between Log and Plan |
| `00a9f6e` | The Sweep area: activity statuses, caught notes to keep or bin, reflection, carry-forward |
| `c37e681` | Prep: tomorrow's printing, setup and chasing, generated from plans and actions |
| `90bc691` | A sweep reflection can spawn a goal |

**Went wrong, put right.**
- Elements marked `hidden` stayed visible inside the panel: LooseLeaf's compositions set `display`, which overrides the attribute. A scoped rule restores it, without `!important`.
- A carried-forward activity vanished when the class's next session had no lesson yet, because the Plan panel only existed with a lesson. The panel now exists whenever there is something carried.
- UX.md's Tab-to-flip would have broken keyboard navigation; Tab flips the panel only when nothing has focus.

## Phase 5: assessment (in progress)

*Goal: a unit taught end to end with components declared in advance; the sweep under three minutes a lesson.*

| Commit | Step |
| --- | --- |
| `0bf637b` | 5.1 The frame: strands and bands, unit components with default next steps, feedback codes, criteria files to share between teachers |
| `a597493` | 5.2 Observations from the seat: long-press, three states, default next step attached, offline through the queue, in the Log and the sweep |
| `424721e` | The plan strip stops counting once the period has ended |
| `43a0aad` | 5.3 Hinge checks: written in the lesson editor with misconception-tagged wrong answers, a bank per unit, the bar's Hinge button with a timed sheet and three decisions, offline through the queue, the judgement in the sweep, and pupils' answers when a unit opts in |
| `bf535a0` | 5.4 Feedback: three parts per lesson for a pupil or a group with a recording moment (permission enforced), codes as a slide, the class-by-component view, self and peer entry in one go, feedback and observations on the pupil page |

**Checked.** On the demo school at iPad size: a long-press opened the sheet for the unit's three components; "Partly" saved with the default next step; "Change" replaced it; the Log showed the observation; after sync the laptop's database held it with the changed step.

**Went wrong, put right.**
- Browser tests found by an element's accessible name broke when keyboard hints were added to button labels; they now match exact text.

**Documentation.** The README became a signpost to `docs/`: user stories with MoSCoW priorities and BDD scenarios, architecture, operations, development, testing, this log, and screenshots of every built journey. `tools/screenshots.py` regenerates the screenshots from the demo school. Capturing them showed that after a lesson's period ended the plan strip kept counting ("836 min in"). Lesson state now carries the period's end, and after it the strip shows the objective with nothing highlighted, as it does when there are no times.

**5.3 checked.** On the demo school at iPad size: the Hinge button was greyed on a lesson without a check and live on one with; the sheet showed the question, the marked answer, each wrong answer's misconception and a running timer; "Moved on" closed it, put "Hinge · moved on" on the bar and in the Log, and reached the laptop; changing it to "Re-taught" offline queued it and synced on reconnecting; H opened the sheet; ✕ in the Log took it back; the sweep showed the room's decision with its minutes. The screenshot tool now captures the sheet.

**5.3 went wrong, put right.**
- The lesson editor's existing test posts no hinge fields, which a required threshold refused. The threshold is optional and defaults to 80%.
- The screenshot tool's mid-lesson captures came out stamped with the real time: it had chosen a future lesson, and sync holds a device clock in the future to now. It now uses the most recent past lesson with a seating plan, cleared of the demo's history first. It had also chosen the hall lesson the demo leaves without a seating plan, so there were no seats to tap.
- The bar's "Hinge · moved on" showed a double gap, because the button's flex gap spaced its two text nodes. The label is now one node.

**5.4 checked.** The screenshot tool loaded every new page in Edge on the demo school without a script error, and each was checked by eye: the lesson's feedback page with a recording moment, the codes slide with nothing about any pupil, the Components tab in greyscale words, the self-and-peer table, and the pupil page's feedback and observations. Saving feedback, the recording permission (pupil and group), self- and peer-assessment and the latest-state rule are covered by the tests rather than clicked through in the browser.

**5.4 changed on review.** The teacher ruled that feedback can be written whenever, not only from the sweep: the pupil page gained a "Write feedback" form that asks which of the pupil's lessons it belongs to, and the room view's ⋯ menu gained "Feedback for this lesson". The room view itself still opens no form (rule 1).

**5.4 went wrong, put right.**
- The codes slide's type was sized for a laptop, not the back of a classroom; it is now the largest step in the scale.
- The demo's class-by-component table was nearly empty with six observations a lesson; the demo now makes ten, so the page shows what it is for.

**Next:**
- 5.5 The exemplar bank gated by permission, and the ipsative timeline on the pupil page.

## Still to come

- **Phase 6:** summative judgements entered against exemplars, report sentences, CSV and clipboard export with a character counter, promote-a-note, parents' evenings.
- **Rollover**, before the second September.
