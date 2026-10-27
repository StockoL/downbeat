# Downbeat: data model and build order

27 October 2026.

## Purpose and the governing rule

Downbeat is a personal classroom app for a secondary music teacher, replacing the Blu-Tack seating plan, the margin shorthand in the mark book, the sticky notes about who to chase, and the July scramble to remember what each pupil did. Single user. Pupil data never leaves the teacher's own devices.

Everything in the app runs at one of three tempos, and every screen belongs to exactly one of them.

**Plan** (desk, before the lesson). Declare the frame: which unit, which lesson in it, which assessment components are in play, the hinge question, who to watch, what needs printing. Mostly reused from the unit, so it takes a minute.

**Catch** (in the room, during). One screen, under two seconds per interaction, never a follow-up question. Tap a seat for a note or an observation; one big button for the hinge decision; a voice note for anything longer. Designed to be ignored for a whole lesson without anything breaking or nagging.

**Sweep** (desk, same day, two minutes). Reconcile the organic lesson with the declared frame: confirm or delete what was caught, set activity statuses, accept carry-forwards, record a class-level hinge judgement from memory, write one line of reflection. The next-steps become the opening of the next plan with that class.

The rule that follows from the research: a record exists because a decision depended on it. Whole-class checks log the decision, not the votes. A pupil observation is stored only with a next step attached. The app holds the frame and catches the residue; it never tries to be present in the moment.

Summative judgement sits outside the loop. Once or twice per strand per year, the teacher listens against exemplars and sets a band with the component evidence in view. The app never computes the band.

## Architecture

Django runs on the Windows laptop and holds the only copy of the data (SQLite). One responsive front end, served as a PWA, is used on the iPad in the room and on the laptop itself at the desk; the layout changes, the features don't. The iPad is offline-first: the day's plans and seating are cached by a service worker, notes and observations queue in IndexedDB, and sync when the laptop is reachable. Last-write-wins with timestamps is enough for one user.

Tailscale joins the two devices across school Wi-Fi (which isolates clients) and issues a real HTTPS certificate for the laptop's hostname, which iOS needs before it will install a PWA with offline support.

Data rules: no public hosting of anything with pupil names; names stored as first name plus surname initial; flag meanings are colours with private labels, never text on the seat; a projector-safe view that shows names only; nightly SQLite copy to OneDrive; full JSON export and a delete-all for the end of a contract. Resource files (slides, audio, PDFs) stay in a folder tree that mirrors the curriculum structure; the app stores paths and links, never the files.

Stack choices to keep it buildable in evenings: Django plus HTMX for most screens, with one hand-written JS component for the seating canvas (pointer events, drag, zones) and a small service-worker/IndexedDB module for the offline queue. No React, no separate API layer beyond the few JSON endpoints the queue needs.

## Data model

Twenty-odd tables in seven groups. Two of them, Note and Observation, carry most of the value; nearly everything else is either structure around them or a view of them. Every table has created/updated timestamps and a UUID primary key so offline-created rows merge cleanly.

### Timetable and sessions

| Table | Fields | Notes |
| --- | --- | --- |
| Timetable | name, week_cycle (1 or 2), periods (JSON: label, start, end) | One active timetable; keep old ones for history |
| Slot | timetable, week (A/B), day, period, room, class | The recurring pattern |
| Session | date, slot (nullable), room, class, lesson (nullable), status (planned/taught/cancelled/moved) | One row per actual occurrence; generated from slots, editable per day. Changing a session's room is the room-change mechanism; the Today view then shows that class's plan for that room, or offers to generate one |

### Rooms and seating

| Table | Fields | Notes |
| --- | --- | --- |
| Room | name, canvas (width, height) | Drawn once and shared by every class taught in it; free-placed, not a grid |
| Seat | room, x, y, label, zone (front/back/side/carpet/keyboard), near_teacher (bool) | Zones are painted once per room; adjacency is computed by radius; zones are also constraints the shuffle can target ("at a keyboard", "near front") |
| SeatingPlan | class, room, name, active_from, active_to | Room is the template, this is one class's arrangement in it; a class may have plans in several rooms. When a session is moved to a room the class has no plan for, the app offers a one-tap generated plan from the class's constraints, seeded by zone from its plan elsewhere (front stays front), to be tidied in the sweep. Duplicate to reshuffle; cover PDF export strips flags, badges and notes and prints names only |
| SeatAssignment | seating_plan, seat, pupil, locked (bool) | Locked seats survive a shuffle; edits go to a recycle bin with undo |

### Pupils, flags, relationships, groups

| Table | Fields | Notes |
| --- | --- | --- |
| Class | name, kind (timetabled/co_curricular), year_group (nullable), pupils (M2M), term dates (nullable) | One table for Y8 set 3 and for choir alike; co-curricular classes can span year groups and sit in the Today list beside lessons |
| Pupil | first_name, surname_initial, year_group, instrument, instrument_teacher, lessons_in_school (bool), remember (free text), recording_permitted (bool), exemplar_reuse_permitted (bool), recordings_delete_by (date) | No photos, no full surname. Recording flags cover the ipsative timeline and the exemplar bank separately, since reuse for teaching is a different purpose from assessment |
| Rotation | name, slot_count, weeks (JSON of dates), slots (JSON: slot order per week) | The peripatetic grid: pull-outs rotate through N slots a term, so a fixed day and period would be wrong most weeks. Imported from the department's spreadsheet or typed |
| PupilRotation | pupil, rotation, slot_index | Derives "out this lesson" for the Today view and the seat |
| SessionAttendance | session, pupil, present (bool) | Used for co-curricular classes (ensemble attendance) and to make the random picker skip absentees; not a replacement for the school register |
| FlagType | label (private), colour, category (attention/adjustment/other), placement_rule (none/front/near_teacher/near_door/away_from_window), what_works (free text) | Meaning lives in the teacher's head; what_works is the minimal pupil-passport note |
| PupilFlag | pupil, flag_type, since, note | Dot on the seat; no text |
| Relationship | pupil_a, pupil_b, kind (keep_apart/pair_well), source (who told you), since, note | Symmetric; drives seating validation and the shuffle |
| Group | class, name, working_on, started, ended | Ends when the unit changes; history kept |
| GroupMember | group, pupil, role | Role optional (drums, keys); history answers "which part did they play last unit" |
| LoanItem | name, kind (headphones/ukulele/cable/other), identifier, condition_note | Equipment the department lends |
| Loan | item, pupil, out_at, due, returned_at, condition_on_return | The weekly headphone hunt |

### Notes and actions

| Table | Fields | Notes |
| --- | --- | --- |
| NoteType | label, icon, is_house_point (bool), is_actionable_default (bool), order | Teacher-defined; five or six on the quick sheet |
| Note | session, pupil (nullable), group (nullable), note_type, text, voice_path, transcript (nullable), actionable (bool), done_at, carried_to_session, promoted_to_mis_at (nullable) | One table, four views: seat badge, pupil inbox, lesson log, actions tab. A group note fans out to members only when explicitly attributed |
| SpokenTo | session, pupil | One row per tap or picker draw; next session highlights those without a row last time. The random picker skips absentees, avoids repeats until everyone has had a turn, and writes a row here |

### Curriculum and plans

| Table | Fields | Notes |
| --- | --- | --- |
| Scheme | year_group, name, strand_framework (JSON of strand names) | Skeleton only; filled as taught |
| Unit | scheme, name, order, lessons_planned, assessment_notes, purpose (Fautley's "why assess this, and what happens to the results?") | |
| LessonPlan | unit, order, objective, starter, main, assessment, differentiation, homework | The template; sessions point at it |
| PlanActivity | lesson_plan, order, text, minutes | The ordered list that makes carry-forward possible |
| ActivityStatus | session, plan_activity, status (done/partial/not_reached), carried_to_session | Set in the sweep |
| Resource | lesson_plan, title, path_or_url, needs_print (bool), copies, setup_note | Feeds the Prep view |
| SessionReflection | session, text, tags (Teachers' Standards / ECF strands), spawned_goal | One or two lines |

### Assessment

| Table | Fields | Notes |
| --- | --- | --- |
| Strand | name, order | Teacher-defined (performing, composing, listening, or whatever the department uses) |
| Band | name, order, description | Teacher-defined vocabulary (Developing/Secure/Expert, 1 to 4, or anything else); nothing in the app assumes a count |
| Component | unit, order, text (pupil-facing, observable), strand, next_step_default, cumulative_of (nullable self-FK) | Three to six per unit; cumulative ordering after Swanwick. A unit's components export and import as a file so a criteria bank can be shared between teachers |
| Observation | session, pupil, component, state (not_yet/partly/secure), assessor (teacher/self/peer), next_step, recording_path | State may move backwards. Stored only with a next step or a recording |
| Feedback | session, pupil or group, component (nullable), done_well, develop, how, voice_path, recording_path, recording_seconds (nullable) | Three-part structure; a Note subtype in practice. The optional timestamp anchors "bar 9, left hand" to a point in the recording |
| FeedbackCode | unit, number, text, component, action | Werry's numbered codes on a slide |
| Check | session, question, distractors (JSON, each tagged with its misconception), threshold, decision (re_taught/moved_on/paired), minutes_in | Class-level log is the record |
| CheckResponse | check, pupil, option | Opt-in only; empty by default |
| Exemplar | unit, component (nullable), level (low/mid/high), recording_path, note, source_pupil (nullable) | Recorded bank of former pupils' work; only from pupils with exemplar_reuse_permitted, and removed when their delete-by date passes |
| SummativeJudgement | pupil, unit, strand, band, evidence_note, judged_at | Entered by the teacher against exemplars; never computed |
| ReportSentence | band, strand, unit (nullable), text | Comment bank keyed on band and strand |

### Goals and reminders

| Table | Fields | Notes |
| --- | --- | --- |
| Goal | text, scope (week/term), target_count, counts_note_type or counts_component, class (nullable), week_start, spawned_from_reflection | "House point in 20 lessons this week" |
| ChecklistItem | text, class (nullable), order | Starter, homework set, exit task |
| ChecklistTick | session, checklist_item, ticked_at | Resets per session |
| PrepItem | session, text, source (resource/action/manual), done_at | The tomorrow view; mostly generated |

### Parents' evenings

| Table | Fields | Notes |
| --- | --- | --- |
| ParentsEvening | name, date, start, end, slot_minutes, location, break_times (JSON) | Teacher defines the evening and the slot length; slots are generated from it |
| EveningSlot | evening, start_time, pupil (nullable), booked_at, attended (null/yes/no), on_the_night_note, follow_up_note | Tap a pupil on the night and the pupil page opens: flags, instrument, latest observations per strand, open actions, the three things to say. Marking a slot not attended spawns an actionable Note ("follow up with parents") so it lands in the actions tab |

Booking happens in the room, from the class list, when a pupil turns up with a sheet: tap the pupil, tap a free slot. If the school books through SchoolCloud or Parents Booking, the slot list imports from CSV instead and the on-the-night view is the same.

Derived views, not tables: the pupil page (flags, instrument, notes, observations, feedback, judgements, newest first); the class-by-component heat view (where the whole class is not yet secure, for curriculum review; states only, never an aggregate); the ipsative timeline (successive recordings of the same piece with the observation at each point); the "missing out" check (pupils with the fewest house points or spoken-to rows this half term); and the cover PDF (names on the room layout, nothing else).

## Build order

Six phases. Each one ends with something used in a real lesson before the next starts, because a fortnight of use will change the next phase more than any amount of planning. Phase 1 is deliberately the whole of "replace the paper", nothing more.

### Phase 1: the room

Timetable, Slot, Session, Class, Pupil, Room, Seat, SeatingPlan, SeatAssignment, NoteType, Note, SpokenTo. Today view that lands on the current session; next-session keypress; seating canvas with drag-and-drop swaps; tap-a-seat note sheet with five preset types including house point; end-of-lesson log; actions tab; spoken-to dimming and next-lesson highlights; absentee-aware random picker that records spoken-to; recycle bin and undo for seat moves and notes; projector-safe view; cover PDF with names only. Laptop only, no PWA yet, Django templates plus HTMX plus the canvas component. Includes a first-run setup screen that creates the timetable, note types, checklist items and flag types from the teacher's own input; no personal values are seeded in migrations, so another teacher starts from a clean install.

Done when: two weeks of real lessons run from it without reaching for the paper plan.

### Phase 2: iPad and offline

PWA manifest and service worker; IndexedDB queue for Note, SpokenTo, SeatAssignment; sync endpoints; Tailscale and HTTPS; responsive layout (plan full-screen on iPad, plan plus side panel on laptop; the breakpoint is a real width, around 1024px, not a device check); keyboard shortcuts on the laptop.

Done when: a lesson can be logged on the iPad with Wi-Fi off and appears on the laptop that evening.

### Phase 3: flags, relationships, groups, goals

FlagType, PupilFlag, Relationship, Group, GroupMember, Goal, ChecklistItem, ChecklistTick. Coloured dots and edges on seats; live validation lines on the seating editor; the shuffle with locks; group tinting and group notes; weekly goal tallies fed by notes; per-lesson checklist; co-curricular sessions in the Today list with ensemble attendance; Rotation and PupilRotation so the seat shows who is out for an instrumental lesson this period; the loan log; the "missing out" check.

Done when: a new seating plan for a class with three keep-aparts can be generated and the house-point tally is visibly nagging by Wednesday.

### Phase 4: plans, curriculum skeleton, prep, sweep

Scheme, Unit, LessonPlan, PlanActivity, ActivityStatus, Resource, SessionReflection, PrepItem. Plan shown beside the seating plan; activity statuses set in the sweep with carry-forward prompts; the tomorrow/Prep view generated from resources, actions and manual items; reflection with tags that can spawn a goal; duplicate-a-unit.

Done when: an unfinished activity from Tuesday appears as a carry-forward prompt on the following Tuesday's plan, and Prep lists tomorrow's printing without being told.

### Phase 5: assessment

Strand, Band, Component, Observation, Feedback, FeedbackCode, Check, CheckResponse, Exemplar. Observation tagging from the seat (component, state, pre-written next step attached); hinge question bank with misconception-tagged distractors, timer, threshold and decision button; feedback codes per unit shown as a whole-class list; self and peer entry in batch from the class list; exemplar bank per unit gated by pupil permission; class-by-component heat view; ipsative timeline on the pupil page; timestamp anchor on feedback; unit component export and import as a shareable criteria file.

Done when: a unit has been taught end to end with components declared in advance, and the sweep took under three minutes per lesson.

### Phase 6: summative and reports

SummativeJudgement, ReportSentence. Band entry per strand per unit with component evidence and exemplars on screen; report assembly from sentences plus the pupil's feedback notes into an editable field; house-style checks (configurable length cap, third person); export as CSV (name, UPN, band per strand, comment) and per-pupil copy-to-clipboard plain text with a live character counter against the MIS limit; promote-a-note: copy a private note's text for entry in the school system and mark it promoted. The app is an export tool here, not the system of record for reports. Parents' evening: define the evening and slot length, book pupils from the class list or import the school's booking CSV, an on-the-night view that opens the pupil page from each slot, attendance marking that creates follow-up actions for absent parents.

Done when: a class's reports are drafted in one sitting from the app and pasted into the school system without rewriting, and a parents' evening is run from the iPad with no paper list.

Phases 3 and 4 can swap depending on what hurts most after Phase 2; 5 and 6 should not move, because 6 is only worth building once a term of 5 has produced evidence.

### Before the second September: rollover

Not a phase, but a job that has to exist before the app has been used for a year, because "not everything rolls over" is the loudest complaint about the one mature offline app in this space. Archive last year's classes, seating plans and sessions as read-only; carry pupils, flags, relationships, instruments and rotation slots forward with a review screen (flags and keep-aparts from a year ago may be stale); close open actions or carry them explicitly; purge recordings past their delete-by date; keep observations and judgements attached to the pupil so the ipsative timeline survives the year boundary.

## Rules the build must not break

1. Any in-lesson capture is at most two taps and never opens a form. If a feature needs more, it belongs in the sweep.
2. The in-lesson screen tolerates a lesson with zero input. No nag, no empty-state prompt, no red count.
3. Whole-class checks store the decision; per-pupil responses are opt-in and off by default.
4. An Observation is only saved with a next step or a recording attached. The default next step comes from the Component, written once at unit setup.
5. Component states can move backwards. No "progress" arithmetic across components, no averages, no percentage secure per pupil. The heat view shows states, never a derived figure.
6. Bands are entered by the teacher, never computed. No flight path, no target grade, no GCSE equivalence anywhere in the schema.
7. Grades and bands are hidden from any pupil-facing or projected view by default.
8. Flags render as colour only. Text labels for flags appear on the pupil page and nowhere else.
9. Projector-safe view and the cover PDF show names and nothing else: no flags, badges, notes or groups. The projector view is the only view that can go full-screen on an external display.
10. Pupil names are first name plus initial. No photographs. No full surnames, no dates of birth, no MIS identifiers beyond an optional UPN used only for export matching.
11. Resource files are referenced, never uploaded into the database.
12. The laptop database is the single source of truth; the iPad holds a cache and a queue, nothing authoritative.
13. Every table has a UUID key and timestamps so offline rows merge without renumbering.
14. The three-strand profile stays uneven in the record. One overall figure is produced only on explicit export and is labelled derived.
15. Recordings are stored only for pupils with recording_permitted, reused as exemplars only with exemplar_reuse_permitted, and deleted when their delete-by date passes. A per-pupil export exists so a subject access request can be answered.
16. Nothing writes to the school's systems. The only door from the private layer to the public one is copy-and-mark-promoted.

## Decisions

Settled 27 Oct 2026: reports are an export tool, not written in the app; band and strand vocabularies are teacher-defined tables so another teacher could use the app without code changes; co-curricular groups are Classes with a kind field, not a separate table; this is a personal project, not the Milestone 4 submission; voice-note transcription is a nice-to-have, recorded as a transcript field on Note and filled in the sweep when a local transcription route is found. On data protection: the same names and flags already pass through a personal device when plans and reports are written, so the app changes where they are kept, not whether; the rules above (local only, initials, colour-only flags, nightly backup, delete-all) are the answer.

Open:

- Which MIS does the school use, and what is its report comment character limit? Sets the default length cap in Phase 6.
- Transcription route: on-device on iPad, or a local model on the laptop during the sweep?
