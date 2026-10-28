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

## Phase 5: assessment

*Goal: a unit taught end to end with components declared in advance; the sweep under three minutes a lesson.*

| Commit | Step |
| --- | --- |
| `0bf637b` | 5.1 The frame: strands and bands, unit components with default next steps, feedback codes, criteria files to share between teachers |
| `a597493` | 5.2 Observations from the seat: long-press, three states, default next step attached, offline through the queue, in the Log and the sweep |
| `424721e` | The plan strip stops counting once the period has ended |
| `43a0aad` | 5.3 Hinge checks: written in the lesson editor with misconception-tagged wrong answers, a bank per unit, the bar's Hinge button with a timed sheet and three decisions, offline through the queue, the judgement in the sweep, and pupils' answers when a unit opts in |
| `bf535a0` | 5.4 Feedback: three parts per lesson for a pupil or a group with a recording moment (permission enforced), codes as a slide, the class-by-component view, self and peer entry in one go, feedback and observations on the pupil page |
| `c317a1f` | Feedback written whenever: from the pupil page and the room view's ⋯ menu as well as the sweep |
| `c6806b0` | 5.5 The exemplar bank, recordings on observations, each pupil's recordings over time, removing recordings that may no longer be kept, and everything held about one pupil in one file |

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

**5.5 checked.** The screenshot tool loaded the Assessment tab with the demo's exemplars, the pupil page with a recording timeline (week 1 "Partly", week 2 "Secure", then the feedback at 1:42) and Settings → Data listing a recording past its delete-by date, without a script error; each was checked by eye. Adding exemplars and recordings, the permission rules, removing references and the per-pupil export are covered by the tests.

**5.5 went wrong, put right.**
- The screenshot tool clears the lesson it uses for the room shots, which took a recording off the pupil's timeline; it now keeps recorded observations, and the demo stamps them inside their lesson.

### Phase 5 review

*Done when: a unit taught end to end with components declared in advance, and the sweep took under three minutes per lesson.*

- **The frame exists before the lesson.** Each demo unit declares its components (with default next steps), feedback codes, a hinge check per lesson and exemplars at three levels, all at the desk on the unit's Assessment tab and in the lesson editor.
- **The room catches it in two taps.** A long-press observes against a component with its next step attached; the Hinge button records the class's decision; nothing in the room asks for more, and a lesson with none of it shows nothing missing.
- **The sweep stays one scroll.** Activities, caught notes and observations to keep or bin, the hinge decision (from memory if it wasn't made in the room), one reflection line. Feedback, self and peer assessment and recordings are their own pages, reached when wanted, so they never lengthen the two-minute sweep.
- **The rules hold in code, not just in the interface.** No observation without a next step or recording (sync and a database constraint); no pupil's hinge answer unless the unit opts in, and only with a decision; no recording without permission, none past the delete-by date once removed; nothing anywhere adds states up.
- **Not yet proven:** the three-minute sweep is a matter of use. It is checked against the demo school until real lessons begin, as every phase's "Done when" has been since the teacher chose to have the app finished first.

**Next:** Phase 6, summative judgements and reports.

## Phase 6: summative and reports

*Goal: a class's reports drafted in one sitting and pasted into the school system without rewriting; a parents' evening run from the iPad with no paper list.*

| Commit | Step |
| --- | --- |
| `2cfa26a` | 6.1 Summative judgements: a band per strand per unit on the class's Judgements tab, with each pupil's evidence and the unit's exemplars in view and nothing suggested; judgements on the pupil page; an optional UPN for the export |

| `35b5bce` | 6.2 Reports: the comment bank and house style in Settings, each pupil's comment drafted from their bands and feedback, edited and kept, with a live count, house-style warnings and Copy; CSV export; promote-a-note |

| `f78871b` | 6.3 Parents' evenings: an evening's slots from its times, booking from the class list in two taps or the school's CSV, and the night on the iPad with came or didn't, a note, and a follow-up action for a family who didn't come |

**6.1 checked.** The screenshot tool loaded 9Y's Judgements tab with the demo's judgements: evidence above each choice, "Not judged" where none was made. Saving, removing, keeping the date on an unchanged save, and the per-pupil export now including judgements are covered by the tests.

**6.2 checked.** In Edge on the demo school: 9Y's Reports tab drafted Ada M's comment from her three bands and her feedback (221 of 600 characters); typing updated the count; Copy put the text on the clipboard and the button said so; Save kept it. On a pupil page, "Copy for the school system" copied the note's words and marked it "promoted 28 Oct". Drafting, the house-style checks, the CSV and settings are covered by the tests.

**6.3 checked.** The screenshot tool loaded the demo's coming evening (22 times, 9 booked), Holly R's booking page from 9Y's list at iPad size, and the night, where "Came" was tapped for the first family, without a script error; each was checked by eye. Making slots, booking rules, the CSV import, the follow-up action and the return-address guard are covered by the tests.

**6.3 went wrong, put right.**
- The night's pupil names showed in the browser's default blue: LooseLeaf styles only links without a class, so the name link takes the theme's link colour itself.

### Phase 6 review

*Done when: a class's reports are drafted in one sitting from the app and pasted into the school system without rewriting, and a parents' evening is run from the iPad with no paper list.*

- **Judgements are the teacher's.** The grid puts each pupil's latest state on each strand's components beside the band choices and the unit's exemplars, and every choice starts at "Not judged".
- **Reports come from the teacher's own words.** The comment bank's sentence for each band judged, then the pupil's latest feedback; edited in place with a live count against the school's limit and house-style warnings; copied one by one, or downloaded as CSV with name, UPN, bands and comment. Nothing writes to the school's system, and nothing produces an overall figure.
- **The evening needs no paper.** Slots from the times, booking from the class list or the school's file, and the night as one list with the pupil page a tap away; a family who didn't come becomes an action in the next lesson.
- **Not yet proven:** both halves of "Done when" are about a real sitting and a real evening, and are checked against the demo school until then. Booking and the night need the laptop reachable; if the school's Wi-Fi fails on the evening, the iPad shows the last copy it saved but can't record.


## Before the second September: rollover

| Commit | Step |
| --- | --- |
| `7a7b24a` | The rollover: a review page that backs up, archives last year's classes read-only, moves pupils up or marks them as left, reviews flags and keep-aparts, closes or carries open actions, and removes recordings past their date; pasting a class list now reuses the pupils who stay |

**Checked.** In Edge on the demo school, a real rollover: the page offered 6 classes, 92 pupils and 9 open actions; applying it wrote a real backup file first, archived all six classes, moved 92 pupils up and closed 9 actions; the Pupils area then listed them under "Archived classes" and Plan had none. Leavers, dropped flags, carried actions, the read-only archive (sync, seating, sweep), pasting next year's lists and a failed backup stopping everything are covered by the tests.

**Went wrong, put right.**
- The tests hung in SQLite's online backup, which waits on the open transaction each test runs inside. Real requests have none (no `ATOMIC_REQUESTS`), and the real backup was proven in the browser run; the rollover's tests record the backup call instead, and the backup itself is tested in `test_data.py`.
- Pasting a class list made a new pupil for every line, which would have doubled every continuing pupil next September. It now reuses the one matching pupil.

## Hardening: errors and bad input

*Raised by the teacher on review: the app had no 404 page and similar safeguards.*

- Its own 400, 403, 404, 500 and expired-form pages, each with a way back, in place of Django's bare defaults.
- A malformed posted id answers 400 instead of 500 (eight views looked up posted ids directly).
- The seating editor no longer pastes an error page into the board; a failed change says it wasn't saved, and why.
- An alert line on every page for any HTMX request that fails.
- The form field limit raised so a whole school's rollover fits.

**Checked.** In Edge on the demo school: forcing the seating editor's request to fail with a server error, and then cutting it off entirely, left the board as it was with "That wasn't saved: something went wrong on the laptop…" and "The laptop can't be reached…"; an unknown address showed the Not found page with Today and Go back. The pages, the 400 for a malformed id and the expired-form page are covered by the tests.

## Review pass

*Asked for once everything in the build order was built: read the whole app as a reviewer would.*

| Commit | Found and put right |
| --- | --- |
| `f8988f8` | No error pages of its own; a malformed id answered 500; the seating editor would paste an error page into the board (see "Hardening: errors and bad input" above) |
| `56303b5` | Deleting a unit whose components had observations failed with a server error, and would otherwise have deleted its summative judgements; a component with observations couldn't be removed cleanly. Records now keep their unit and component, and the refusal says why |
| `dd3b3c2` | On an iPad the room's seats were 35 to 43px tall, under UX.md's 44-point minimum. Below desk width the canvas grows taller to fit them, without widening or overlapping |
| docs | The docs checked against the code: test counts, story statuses and commit placeholders corrected |

**Checked and found sound.** No unescaped output, no HTML from script except the laptop's own escaped templates, no raw SQL, no CSRF exemption, every POST form carries its token and every new-window link has `noopener`; `manage.py check --deploy` passes with its three documented silences; every protected key's parent is either guarded in its view or never deleted; at four iPad sizes and a laptop, nothing in the bar is under 44px, nothing overflows sideways, no seat hides under the bar or overlaps another, and the hinge sheet fits.

## Still to come

- **The real-iPad check** from Phase 2: install from the `ts.net` address, a lesson with the Wi-Fi off, and the laptop catching up.
- **Real use.** Every phase's "Done when" has been checked against the demo school; the two-minute sweep, a report season and a parents' evening are proven only by doing them.
- **The open questions** in BUILD_ORDER: the school system's report character limit (set in Settings → Reports once known) and a transcription route for voice notes.
