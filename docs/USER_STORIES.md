# User stories

What Downbeat does, for whom, and how we know it does it. Each story has a MoSCoW priority, its build status, and acceptance criteria written as BDD scenarios (Given / When / Then). The scenarios describe behaviour the teacher can see; the automated tests that hold them in place are mapped in [TESTING.md](TESTING.md).

The source for every story is [BUILD_ORDER.md](BUILD_ORDER.md) and [UX.md](UX.md). Where the build settled a detail the spec left open, the scenario follows [DECISIONS.md](DECISIONS.md).

## Contents

- [People](#people)
- [How priorities were set](#how-priorities-were-set)
- [MoSCoW summary](#moscow-summary)
- [Won't have](#wont-have)
- Stories: [Setting up](#1-setting-up) · [Catch: in the room](#2-catch-in-the-room) · [Plan: at the desk, ahead](#3-plan-at-the-desk-ahead) · [Sweep: at the desk, same day](#4-sweep-at-the-desk-same-day) · [Pupils](#5-pupils) · [Reports and parents' evenings](#6-reports-and-parents-evenings) · [Data and safety](#7-data-and-safety)

## People

| Who | Their need |
| --- | --- |
| **The teacher** | A secondary music teacher, the only user. Circulates with an iPad during practical lessons; plans and sweeps at a laptop. Wants the frame of each lesson held for them and the residue caught, without the app asking for attention mid-lesson. |
| **A cover teacher** | Takes a class when the teacher is away. Needs to know who sits where, and nothing else. |
| **The class** | Sees the projector. Must never see flags, notes, grades or who has been spoken to. |
| **A pupil or parent** | Has a right to know what is held about the pupil, and for recordings to be used only as permitted. |
| **Another teacher** | Might install Downbeat, or receive a unit's criteria file. Needs a clean start with nothing of the first teacher's in it. |

## How priorities were set

The build is phased, and each phase ends with a "Done when" test. Priorities follow from that and from the rules in BUILD_ORDER:

- **Must have.** The phase's "Done when" test can't pass without it, or it enforces one of the sixteen rules (privacy, no computed grades, two-tap capture). Without it the app would be unsafe or would fail at its own purpose.
- **Should have.** In the build order and valuable every week, but the phase's goal is reachable without it, or there is a workable manual alternative (the paper register, a spreadsheet).
- **Could have.** Useful, cheap once the foundations exist, or explicitly a nice-to-have in the spec. First to be dropped if time runs short.
- **Won't have.** Deliberately excluded, usually because it would break a rule or turn a personal tool into a school system. Listed so the absence is a decision, not an oversight.

Status key: **Built** (with the step that built it), **Planned** (with its phase), **Partly** (what exists and what doesn't).

## MoSCoW summary

| Area | Must | Should | Could |
| --- | --- | --- | --- |
| Setting up | US-01, 02, 03, 04, 05 | US-06 | US-07 |
| Catch | US-10, 11, 12, 13, 14, 15, 16, 17 | US-18, 19, 20, 21, 22, 23, 24, 25 | US-26, 27, 28 |
| Plan | US-30, 31, 32, 33, 34, 42 | US-35, 36, 37, 38, 39, 43 | US-40, 41 |
| Sweep | US-50, 51, 52, 53 | US-54, 55 | US-56, 57 |
| Pupils | US-60 | US-61, 62, 63, 66 | US-64, 65 |
| Reports and evenings | US-70, 71, 72, 75 | US-73, 74 | |
| Data and safety | US-80, 81, 82, 83, 84, 85 | US-86 | |

Of the Must haves, all but reports (US-70 to 72) and rollover (US-75) are built: Phase 6 and the job before the second September.

## Won't have

| Excluded | Why |
| --- | --- |
| A computed band, average, percentage secure, flight path or target grade | Rules 5 and 6: bands are the teacher's judgement against exemplars, and component states may move backwards |
| Writing to the school's MIS or any school system | Rule 16: the only door out is copy-to-clipboard, CSV and mark-as-promoted |
| Pupil photographs, full surnames, dates of birth | Rule 10: minimum identifying data on a personal device |
| Flag labels on seats, the projector or the cover PDF | Rules 8 and 9: a flag's meaning lives in the teacher's head |
| Cloud hosting or sync through a third party | Pupil data stays on the teacher's own devices; Tailscale carries traffic between them but the data never rests elsewhere |
| More than one user, or a pupil or parent login | A personal tool, not a school platform |
| Uploading resource files into the app | Rule 11: files stay in the curriculum folder tree; the app stores paths |
| Per-pupil hinge responses by default | Rule 3: the class-level decision is the record; per-pupil responses are opt-in |
| Nags, red counts or empty-state prompts in the room | Rule 2: a lesson with zero input is a valid lesson |
| Personal values seeded in migrations | A second teacher must start from a clean install |

---

## 1. Setting up

### US-01 First-run setup from my own input
**As** the teacher, **I want** to set up my timetable, note types and first room on first use, **so that** the app holds my school's structure and nothing I didn't put there.
Must · Built (Phase 1, step 2; account added Phase 2)

```gherkin
Scenario: A fresh install leads to setup
  Given Downbeat has just been installed
  When I open any page
  Then I am taken to the first-run setup
  And no field is pre-filled with a value

Scenario: Setup saves everything or nothing
  Given I have filled in my account, periods and note types
  But my first room has an invalid size
  When I save the setup
  Then nothing is saved
  And I am shown what to fix
```

### US-02 A timetable that generates my lessons
**As** the teacher, **I want** to enter my one- or two-week timetable once and generate the term's lessons from it, **so that** each day's lessons are waiting for me.
Must · Built (Phase 1, step 3)

```gherkin
Scenario: Generating a half term on a two-week timetable
  Given a two-week timetable with 8X in M2 on Monday of week A
  When I generate sessions from 2 November, which is week A
  Then 8X has a lesson in M2 on 2 November and 16 November but not 9 November

Scenario: Generating twice is safe
  Given sessions have been generated for this half term
  When I generate the same dates again
  Then no session is duplicated or overwritten
```

### US-03 Class lists that keep only an initial
**As** the teacher, **I want** to paste a class list from the register, **so that** I can add thirty pupils at once without storing their surnames.
Must · Built (Phase 1, step 3)

```gherkin
Scenario: Pasting full names
  Given the 8X class page
  When I paste "Aleya Khan" and "Jojo Price" on separate lines
  Then the class has pupils "Aleya K" and "Jojo P"
  And no full surname is stored anywhere
```

### US-04 Draw a room once
**As** the teacher, **I want** to place seats freely on a room plan, paint zones and mark where I stand, **so that** every class taught there can use the same layout.
Must · Built (Phase 1, step 4)

```gherkin
Scenario: Drawing a keyboard room
  Given a new room
  When I add seats, drag them into place and paint six of them "keyboard"
  Then every class's seating plan in that room uses those seats and zones
```

### US-05 Sign in once on the iPad
**As** the teacher, **I want** a password on the app that doesn't ask again mid-lesson, **so that** the iPad is protected without getting in my way.
Must · Built (Phase 2, step 2.1)

```gherkin
Scenario: The session outlasts a term
  Given I signed in on the iPad
  When I open Downbeat in a lesson eight weeks later
  Then I am not asked for my password

Scenario: Guessing is slowed
  Given five wrong passwords have been tried from one address
  When a sixth attempt is made
  Then sign-in is paused for five minutes
```

### US-06 Flags and checklist at setup
**As** the teacher, **I want** to define my flag types and lesson checklist during setup if I choose, **so that** the room is ready on day one.
Should · Built (Phase 3)

```gherkin
Scenario: Optional sections
  Given I am on the first-run setup
  When I leave the flags and checklist sections empty
  Then setup still completes
  And I can add them later in Settings
```

### US-07 Import a rotation from the department spreadsheet
**As** the teacher, **I want** to paste the instrumental lesson rotation, **so that** I don't have to retype it.
Could · Built (Phase 3)

```gherkin
Scenario: A bad row is named
  Given a rotation of five slots
  When I paste a row with a period the timetable doesn't have
  Then nothing is saved
  And the row number and the unknown period are shown
```

---

## 2. Catch: in the room

### US-10 Land on the lesson I'm teaching
**As** the teacher, **I want** opening the app to land on the lesson happening now, **so that** I reach the room with zero taps.
Must · Built (Phase 1, step 6)

```gherkin
Scenario: A lesson is live
  Given it is 10:55 and 8X is timetabled for P3, 10:50 to 11:50
  When I open Downbeat
  Then I see 8X's room view

Scenario: Between lessons
  Given no lesson is live
  When I open Downbeat
  Then I see today's lessons in period order with the next one outlined
```

### US-11 A note in two taps
**As** the teacher, **I want** to tap a pupil's seat and then one note button, **so that** I can record a house point or a concern while circulating.
Must · Built (Phase 1, step 7)

```gherkin
Scenario: A house point
  Given I am in 8X's room view
  When I tap Aleya K's seat
  And I tap "House point"
  Then the sheet closes
  And a house point badge shows on Aleya K's seat
  And the Log shows the time, "Aleya K" and "House point"
  And no form was opened
```

### US-12 Captures work without the Wi-Fi
**As** the teacher, **I want** everything I capture on the iPad to be kept when the network drops, **so that** school Wi-Fi never costs me a note.
Must · Built (Phase 2, step 2.3)

```gherkin
Scenario: Offline then online
  Given the iPad cannot reach the laptop
  When I record three notes and an absence
  Then they show in the room at once
  And the bar says "4 saved on this device" in neutral text
  When the laptop becomes reachable
  Then the laptop holds each capture exactly once, at the time I made it
  And the bar message disappears
```

### US-13 A lesson with no input is fine
**As** the teacher, **I want** the room view to stay calm if I record nothing, **so that** the app never becomes another thing to keep up with.
Must · Built (Phase 1; rule 2)

```gherkin
Scenario: Nothing recorded
  Given a lesson in which I have recorded nothing
  When I look at the room view
  Then there is no prompt, no red count and no empty-state message
```

### US-14 Undo a mistaken note
**As** the teacher, **I want** to remove a note from the Log and undo that removal, **so that** a slip of the finger costs one tap.
Must · Built (Phase 1, step 7)

```gherkin
Scenario: Remove and undo
  Given the Log shows a house point for the wrong pupil
  When I tap its ✕
  Then it disappears from the Log and the seat
  When I tap Undo
  Then it is back
```

### US-15 Actions follow the class
**As** the teacher, **I want** notes that need doing to stay open until I tick them, **so that** "chase homework" isn't lost between lessons.
Must · Built (Phase 1, step 7)

```gherkin
Scenario: Carried to the next lesson
  Given an open "Chase homework" action for Tariq L in Tuesday's 9Y lesson
  When I open Thursday's 9Y lesson and tap Actions
  Then "Chase homework" for Tariq L is listed
  When I tap it done
  Then it no longer appears in any lesson
```

### US-16 Observe against the unit's components
**As** the teacher, **I want** to long-press a seat and tap a state against one of the unit's components, **so that** formative evidence is caught with its next step in two taps.
Must · Built (Phase 5, step 5.2)

```gherkin
Scenario: An observation with its default next step
  Given 9Y's lesson belongs to a unit with the component "Plays a riff in time with the band"
  And that component's default next step is "Lock in with the drummer's snare"
  When I long-press Dev N's seat
  And I tap "Partly" for that component
  Then the observation is saved with the next step "Lock in with the drummer's snare"
  And the sheet shows that next step with a "Change" option

Scenario: No next step, no observation
  Given an observation arrives at the laptop without a next step or a recording
  Then it is refused

Scenario: A lesson without components
  Given the lesson has no unit, or its unit has no components
  When I long-press a seat
  Then nothing different happens and no Observe button is shown
```

### US-17 Log the hinge decision
**As** the teacher, **I want** one button that shows the lesson's hinge question with a timer and lets me record what I decided, **so that** the decision is the record, not the votes.
Must · Built (Phase 5, step 5.3)

```gherkin
Scenario: Moving on
  Given the lesson plan has a hinge check
  When I tap the hinge button
  Then the question, the right answer, each wrong answer with its misconception, and a running timer are shown
  When I tap "Moved on"
  Then the sheet closes and the bar reads "Hinge · moved on"
  And the Log shows "Hinge · moved on"
  And the decision and the minutes into the lesson are recorded for the class
  And no pupil's answer is recorded

Scenario: Changing my mind
  Given I recorded "Re-taught"
  When I open the hinge check again and tap "Paired"
  Then the lesson has one decision, "Paired"

Scenario: No check planned
  Given the lesson has no hinge check
  Then the hinge button is in its usual place, greyed
```

### US-18 Spoken to, and who I missed last time
**As** the teacher, **I want** to mark who I've spoken to and see who I didn't get to last lesson, **so that** the same quiet pupils aren't overlooked every week.
Should · Built (Phase 1, step 8)

```gherkin
Scenario: Highlighting last time's gaps
  Given last 8X lesson I marked everyone spoken to except Mia T
  When I open this 8X lesson
  Then Mia T's seat has a thicker edge

Scenario: Unused last time
  Given last 8X lesson I marked nobody as spoken to
  When I open this 8X lesson
  Then nobody is highlighted
```

### US-19 A fair random picker
**As** the teacher, **I want** a picker that draws from present pupils who haven't had a turn, **so that** cold-calling is fair and recorded.
Should · Built (Phase 1, step 8; offline in Phase 2)

```gherkin
Scenario: Skipping the absent and the already asked
  Given Jojo P is absent and Aleya K has been spoken to
  When I tap Pick
  Then neither Jojo P nor Aleya K is drawn
  And the drawn pupil is marked spoken to

Scenario: Calling an empty chair
  Given the picker has drawn Sam R, who is not here
  When I tap "Sam R is absent"
  Then Sam R is marked absent, the draw is taken back and another pupil is drawn
```

### US-20 Mark someone absent
**As** the teacher, **I want** to mark a pupil absent from their seat, **so that** the picker skips them. It is not the register.
Should · Built (Phase 1, step 8)

```gherkin
Scenario: Absent from the seat
  When I tap a seat and then "Absent"
  Then the seat fades with the name struck through
```

### US-21 Next lesson in one tap
**As** the teacher, **I want** a Next button (or the N key), **so that** I can move to the next class without going back to Today.
Should · Built (Phase 1, step 6)

```gherkin
Scenario: Skipping a cancelled lesson
  Given my next lesson today is cancelled and the one after is 7R
  When I tap Next
  Then I see 7R's room view
```

### US-22 The plan beside the room
**As** the teacher, **I want** the current and next activity at a glance and the full plan one tap away, **so that** I keep track of time without reading a document.
Should · Built (Phase 4, step 4.2)

```gherkin
Scenario: The strip
  Given the lesson started 12 minutes ago and the first activity is 10 minutes long
  Then the strip names the second activity as now, how far in we are, and the third as next
  And the second activity is highlighted in the plan
  When I tap the strip
  Then the panel shows the plan, and the strip shows the last Log line
```

### US-23 Goals and checklist as quiet counters
**As** the teacher, **I want** my weekly goals and lesson checklist as counters on the bar, **so that** I'm reminded without being nagged.
Should · Built (Phase 3)

```gherkin
Scenario: A weekly house-point goal
  Given a goal of a house point in 20 lessons this week
  And 6 lessons this week have had a house point
  When I give a house point in this lesson
  Then the counter reads "★ 7/20" in plain text, with no colour
```

### US-24 Ensemble register
**As** the teacher, **I want** a register for choir and band, **so that** attendance at rehearsals is recorded where it matters.
Should · Built (Phase 3)

```gherkin
Scenario: Everyone here
  Given a choir rehearsal
  When I open the register and tap "Everyone here"
  Then every unmarked member is marked present
  And members I marked absent stay absent
```

### US-25 See who is out for an instrumental lesson
**As** the teacher, **I want** pupils out at their instrumental lesson to show as greyed seats, **so that** I don't call on them or mark them absent.
Should · Built (Phase 3)

```gherkin
Scenario: A rotation slot this period
  Given Priya S's violin lesson rotation puts her out in P3 this week
  When I open P3's room view
  Then her seat is greyed with a strike and a dashed edge
  And the picker does not draw her
```

### US-26 Group notes
**As** the teacher, **I want** to note something about a group as a whole, **so that** "no structure yet" can be recorded for the drum group without five taps.
Could · Built (Phase 3)

```gherkin
Scenario: A note for a group
  Given 9Y has an active group "Band 2"
  When I tap the "Band 2" chip and a note type
  Then one note is recorded for the group, not one per member
```

### US-27 Laptop keyboard shortcuts
**As** the teacher at the laptop, **I want** keyboard shortcuts, **so that** I can work the room view without the mouse.
Could · Built (Phase 2, step 2.4)

```gherkin
Scenario: A note by keyboard
  Given a pupil's sheet is open
  When I press 1
  Then the first note type is recorded
  And no shortcut fires while I am typing in a field
```

### US-28 A voice note for anything longer
**As** the teacher, **I want** to record a short voice note against a pupil, **so that** something too long for a button is still caught.
Could · Planned (no phase set; transcription route still open)

```gherkin
Scenario: Transcribed later
  Given I recorded a voice note for Aleya K
  When I sweep the lesson
  Then I can play it and add a transcript
```

---

## 3. Plan: at the desk, ahead

### US-30 Seating plans I can edit by dragging
**As** the teacher, **I want** to drag pupils into seats, swap them, lock some and undo mistakes, **so that** making a plan is quicker than paper.
Must · Built (Phase 1, step 5)

```gherkin
Scenario: Swap and undo
  Given Aleya K and Jojo P are seated
  When I drag Aleya K onto Jojo P
  Then they have swapped seats
  When I tap Undo
  Then they are back where they were

Scenario: Locked seats hold
  Given Aleya K's seat is locked
  When I drag another pupil onto it
  Then Aleya K stays
```

### US-31 Keep-apart and pair-well, checked as I drag
**As** the teacher, **I want** to record who should be kept apart or paired and see a line when a plan breaks that, **so that** I don't seat a known problem pair together by accident.
Must · Built (Phase 3)

```gherkin
Scenario: A broken keep-apart
  Given Tom B and Lee W are to be kept apart
  When I seat them next to each other
  Then a warning line joins their seats
  And the summary says so in words
```

### US-32 Shuffle that never breaks a hard rule
**As** the teacher, **I want** a shuffle that keeps locked seats and keep-apart pairs, **so that** a fresh plan is one tap and always safe.
Must · Built (Phase 3; "Done when" for Phase 3)

```gherkin
Scenario: Three keep-aparts
  Given a class with three keep-apart pairs and two locked seats
  When I tap Shuffle
  Then no keep-apart pair are neighbours
  And the locked pupils have not moved

Scenario: Impossible
  Given the locks leave no arrangement that keeps everyone apart
  When I tap Shuffle
  Then the plan is unchanged
  And I am told to unlock someone or add seats
```

### US-33 A plan when the room changes
**As** the teacher, **I want** a one-tap plan when a class is moved to a room it has no plan for, **so that** a room change doesn't mean a blank screen.
Must · Built (Phase 1, step 5)

```gherkin
Scenario: Front stays front
  Given 8X has a plan in M2 and is moved to the hall today
  When I open the lesson's room view
  Then a quiet line offers "Seat by zone from M2"
  When I tap it
  Then pupils at the front of M2 are at the front of the hall
```

### US-34 Schemes, units and lessons that sessions point at
**As** the teacher, **I want** units of ordered lessons with activities and resources, attached to my classes' sessions, **so that** each lesson's plan is waiting in the room.
Must · Built (Phase 4, step 4.1)

```gherkin
Scenario: Filling a class's lessons
  Given 8X has taught lessons 1 to 3 of "Blues"
  When I choose "Fill in order" with "Blues"
  Then 8X's next sessions without a lesson get lessons 4, 5 and 6
```

### US-35 Flags as colour
**As** the teacher, **I want** private flag types shown as a coloured edge on the seat, **so that** I remember adjustments without anyone reading a label over my shoulder.
Should · Built (Phase 3)

```gherkin
Scenario: Colour only in the room
  Given Mia T has the flag "Hearing: front left" in colour 3
  When I look at her seat
  Then it has a colour 3 edge and no text about the flag
  And the label appears only on her pupil page
```

### US-36 Groups with tints
**As** the teacher, **I want** working groups with optional roles, tinted on the seats, **so that** I can see the groups at a glance and remember who played what last unit.
Should · Built (Phase 3)

```gherkin
Scenario: Ending a group keeps its history
  Given "Band 2" with Dev N on drums
  When I end the group
  Then it no longer tints seats
  And Dev N's pupil history still shows drums in "Band 2"
```

### US-37 Duplicate a unit
**As** the teacher, **I want** to copy a unit with its lessons, resources and components, **so that** next year starts from this year.
Should · Built (Phase 4; components added in 5.1)

```gherkin
Scenario: A full copy
  When I duplicate "Blues"
  Then "Blues (copy)" has the same lessons, activities, resources, components and feedback codes
  And the original is unchanged
```

### US-38 Components with default next steps
**As** the teacher, **I want** to declare each unit's components with a pupil-facing description and a default next step, **so that** observations in the room take one tap.
Should · Built (Phase 5, step 5.1)

```gherkin
Scenario: Declaring a component
  Given the unit "Blues"
  When I add "Keeps a steady pulse" under Performing with next step "Play with the click"
  Then it is offered on the observation sheet in every Blues lesson
```

### US-39 Duplicate a plan to reshuffle
**As** the teacher, **I want** to start a new seating plan from today and keep the old one, **so that** last half term's arrangement stays on record.
Should · Built (Phase 3)

```gherkin
Scenario: History by date
  When I duplicate 8X's M2 plan as a new plan from today
  Then lessons before today use the old plan and lessons from today use the new one
```

### US-40 Share criteria with another teacher
**As** the teacher, **I want** to export a unit's components as a file and import one, **so that** a department can share a criteria bank.
Could · Built (Phase 5, step 5.1)

```gherkin
Scenario: A file from another version
  When I import a criteria file from an unknown version
  Then nothing is added and I am told why
```

### US-41 An exemplar bank
**As** the teacher, **I want** recordings of former pupils' work at low, mid and high per component, **so that** I can show the class what good looks like and judge against it.
Could · Built (Phase 5, step 5.5)

```gherkin
Scenario: Only with permission
  Given Sam R does not have exemplar reuse permitted
  Then Sam R isn't offered as the source of an exemplar, and one naming Sam R is refused

Scenario: The department's own
  When I add a "high" exemplar for "Plays a riff in time" with no pupil named
  Then it is listed on the unit's Assessment tab with its recording and what to listen for
```

### US-42 Hinge checks, written once and reused
**As** the teacher, **I want** to write a lesson's hinge question with wrong answers that each name a misconception, and start another lesson's check from it, **so that** a good question is written once.
Must · Built (Phase 5, step 5.3)

```gherkin
Scenario: Every wrong answer names its misconception
  Given I am editing a lesson
  When I add a wrong answer without saying which misconception it shows
  Then the lesson isn't saved and I am asked for the misconception

Scenario: The unit's bank
  Given lesson 1 of "Blues" has a hinge check
  When I open lesson 2 and choose "Start from another lesson's check"
  Then lesson 2 has a copy I can change without changing lesson 1
  And the unit's Assessment page lists both
```

### US-43 Feedback codes on the projector
**As** the teacher, **I want** a unit's numbered feedback codes as a slide, **so that** the whole class can look up what their number means.
Should · Built (Phase 5, step 5.4)

```gherkin
Scenario: A slide with nothing about any pupil
  Given "Riffs" has codes 1 and 2
  When I choose "Feedback codes" from the room view's ⋯ menu
  Then a new window shows "1 Count in before you start" and "2 …" in large type, black on white
  And no pupil's name appears
```

---

## 4. Sweep: at the desk, same day

### US-50 Activity statuses with carry-forward
**As** the teacher, **I want** to mark each activity done, partly done or not reached, **so that** unfinished work appears in the class's next lesson.
Must · Built (Phase 4, step 4.3; "Done when" for Phase 4)

```gherkin
Scenario: Tuesday to Tuesday
  Given Tuesday's 8X lesson had "Swap parts" not reached
  When I sweep it with "carry to next lesson" ticked
  Then the next 8X lesson's plan shows "Carried forward: Swap parts, from Tue"
  And this happens even if that lesson has no plan yet
```

### US-51 Keep or bin what was caught
**As** the teacher, **I want** to see the lesson's notes and observations and bin any that were wrong, **so that** the record is clean before I leave.
Must · Built (Phase 4, step 4.3; observations in 5.2)

```gherkin
Scenario: Binning one observation
  Given the sweep lists two observations
  When I tick Bin on one and save
  Then only the other remains on the pupil's record
```

### US-52 Prep for tomorrow without being told
**As** the teacher, **I want** a list of what to print, set up and chase for tomorrow, built from my plans and open actions, **so that** I'm not caught out at 8:30.
Must · Built (Phase 4, step 4.4; "Done when" for Phase 4)

```gherkin
Scenario: Printing found from the plan
  Given tomorrow's 8X lesson has a resource "Lyric sheet" marked print, 30 copies
  When I open Prep
  Then it lists "Print 30 × Lyric sheet"
  When I tick it
  Then it stays ticked when I come back
```

### US-53 Record the hinge judgement from memory
**As** the teacher, **I want** to record the class-level hinge decision in the sweep if I didn't in the room, **so that** the record exists without a tap mid-lesson.
Must · Built (Phase 5, step 5.3)

```gherkin
Scenario: Judged afterwards
  Given the lesson had a hinge check with no decision recorded
  When I sweep it and choose "Re-taught"
  Then the decision is recorded for the class, with no minutes into the lesson

Scenario: Confirming the room's decision
  Given I tapped "Moved on" 23 minutes into the lesson
  When I sweep it
  Then "Moved on" is chosen and the sweep says "Decided in the lesson, 23 min in"
```

### US-54 One line of reflection
**As** the teacher, **I want** to write a one-line reflection with optional Teachers' Standards tags, **so that** I have evidence for my own development without a separate log.
Should · Built (Phase 4, step 4.3)

```gherkin
Scenario: Saving marks the lesson swept
  When I write a reflection and save the sweep
  Then the session shows as swept on the Sweep list
  And a planned session becomes taught
```

### US-55 Give a group note to each member
**As** the teacher, **I want** to attribute a group note to each member explicitly, **so that** it appears in their records only when I mean it to.
Should · Built (Phase 4, step 4.3)

```gherkin
Scenario: Giving twice adds nothing
  Given a note for "Band 2" with four members
  When I tap "Give to each member" twice
  Then each member has exactly one copy
```

### US-56 Turn a reflection into a goal
**As** the teacher, **I want** to turn a reflection into a weekly goal, **so that** "I gave no house points to 9Y" becomes something I act on.
Could · Built (Phase 4, step 4.5)

```gherkin
Scenario: Spawning a goal
  When I tick "Turn this into a goal" and give a note type and target
  Then a weekly goal starting today appears on the bar
  And the reflection reads "Became the goal …"
```

### US-57 Each pupil's hinge answer, when the unit asks for it
**As** the teacher, **I want** to record each pupil's answer to a hinge check in the sweep for units where I've chosen to, **so that** I can see who holds which misconception when it matters, without it becoming the default.
Could · Built (Phase 5, step 5.3)

```gherkin
Scenario: Off by default
  Given the unit doesn't record pupils' answers
  When I sweep a lesson with a hinge check
  Then there is no per-pupil grid

Scenario: Kept only with a decision
  Given the unit records pupils' answers
  When I enter answers but leave the decision as "Not asked"
  Then the answers aren't saved and I'm told why
```

---

## 5. Pupils

### US-60 Everything about one pupil, in one place
**As** the teacher, **I want** a pupil page with their flags, instrument, notes, observations, feedback, recordings and loans, **so that** I can prepare for a conversation at the desk.
Must · Partly (built through Phase 5; judgements join in Phase 6)

```gherkin
Scenario: The only place labels appear
  When I open Mia T's pupil page
  Then her flags are shown with their labels, notes and what works
```

### US-61 Who is missing out
**As** the teacher, **I want** each class's pupils listed by fewest house points and turns this half term, **so that** I notice who I've overlooked.
Should · Built (Phase 3)

```gherkin
Scenario: Plain counts
  When I open 8X's "Missing out" tab
  Then pupils are listed fewest house points first, with turns and absences beside them
  And there is no score, colour or warning
```

### US-62 Feedback in three parts
**As** the teacher, **I want** to record feedback as done well, develop and how, optionally anchored to a moment in a recording, **so that** feedback is specific and actionable.
Should · Built (Phase 5, step 5.4)

```gherkin
Scenario: Anchored to bar 9
  Given Ada M's family has agreed to recordings
  When I write feedback for Ada M with "How: lock to the hi-hat", the recording's path and "1:42"
  Then her pupil page shows the three parts and "Music/Recordings/9Y/riff-week-1.m4a at 1:42"

Scenario: No permission, no recording
  Given Sam R's family has not agreed to recordings
  When I add a recording to Sam R's feedback
  Then it isn't saved and I'm told recordings aren't permitted for Sam R

Scenario: For a group
  When I write feedback for "Band 1"
  Then it shows on each member's pupil page, labelled with the group

Scenario: Whenever, from the pupil page
  Given I am on Ada M's pupil page
  When I open "Write feedback", keep her latest lesson and write "To develop: steadier fills"
  Then the feedback belongs to that lesson and shows on her page
```

### US-63 The class-by-component heat view
**As** the teacher, **I want** to see where the whole class is not yet secure, **so that** I can review the unit, not rank pupils.
Should · Built (Phase 5, step 5.4)

```gherkin
Scenario: States, never figures
  When I open 9Y's Components tab for "Riffs"
  Then each cell shows a pupil's latest state on a component, in words
  And no total, average or percentage appears anywhere

Scenario: Whose judgement
  Given pupils have self-assessed
  When I choose "Assessed by: Self"
  Then the cells show their own latest states, kept apart from mine
```

### US-64 Self and peer assessment in batch
**As** the teacher, **I want** to enter self- and peer-assessments from the class list in one pass, **so that** pupils' own judgements sit beside mine.
Could · Built (Phase 5, step 5.4)

```gherkin
Scenario: Marked as self-assessed
  Given 9Y's lesson on Tuesday was from "Riffs"
  When I choose that lesson, "Plays a riff in time" and "Self", and mark each pupil's answer
  Then each is recorded as a self-assessment with the component's next step
  And pupils left at "None" have nothing recorded
```

### US-65 The equipment loan log
**As** the teacher, **I want** to record who has which headphones or ukulele, **so that** the weekly hunt is a list, not a memory test.
Could · Built (Phase 3)

```gherkin
Scenario: One loan at a time
  Given headphones 3 are lent to Jojo P
  Then headphones 3 cannot be lent to anyone else until returned
```

### US-66 A pupil's progress against themselves
**As** the teacher, **I want** a pupil's recordings in order with what I heard each time, **so that** I can hear and show their progress against their own earlier work.
Should · Built (Phase 5, step 5.5)

```gherkin
Scenario: Oldest first, one line per piece
  Given Ada M was recorded playing the riff on 22 and 27 October
  When I open her pupil page
  Then "Recordings over time" lists the riff on 22 October ("Partly") before 27 October ("Secure")
  And a recording that is a web address opens at its moment

Scenario: No permission, no recordings
  Given Sam R's family has not agreed to recordings
  Then Sam R's page offers no "Add a recording" and says why
```

---

## 6. Reports and parents' evenings

### US-70 Enter a band, never compute one
**As** the teacher, **I want** to set a band per strand per unit with the component evidence and exemplars beside me, **so that** the judgement is mine and evidenced.
Must · Planned (Phase 6)

```gherkin
Scenario: No suggested band
  When I open the judgement grid for 9Y
  Then each pupil's observations are shown beside the band choices
  And no band is pre-selected or suggested
```

### US-71 Draft reports from sentences
**As** the teacher, **I want** report text assembled from my comment bank and the pupil's feedback, with a live character count, **so that** a class's reports take one sitting.
Must · Planned (Phase 6)

```gherkin
Scenario: Within the MIS limit
  Given the length cap is 600 characters
  When I edit a pupil's assembled report
  Then a counter shows the characters used against 600
  And "Copy" puts the text on the clipboard
```

### US-72 Export for the school system
**As** the teacher, **I want** a CSV of names, bands per strand and comments, **so that** I can enter them into the MIS. Downbeat never writes to it.
Must · Planned (Phase 6)

```gherkin
Scenario: The derived figure is labelled
  When I export a class's CSV with an overall figure
  Then that column is labelled as derived
```

### US-73 Promote a note to the school system
**As** the teacher, **I want** to copy a private note for entry in the school's system and mark it promoted, **so that** I know what has been shared.
Should · Planned (Phase 6)

```gherkin
Scenario: Marked, not sent
  When I promote a note
  Then its text is copied to the clipboard and it shows as promoted
  And nothing is sent anywhere
```

### US-74 Run a parents' evening from the iPad
**As** the teacher, **I want** to book slots from the class list and open each pupil's page on the night, **so that** I need no paper list.
Should · Planned (Phase 6)

```gherkin
Scenario: A family doesn't come
  When I mark a slot not attended
  Then an action "Follow up with parents" is added to that pupil
```

### US-75 Roll over to a new school year
**As** the teacher, **I want** last year archived and pupils, flags and rotations carried forward with a review, **so that** September doesn't start from nothing or from stale data.
Must · Planned (before the second September)

```gherkin
Scenario: Stale flags are reviewed
  When I run the rollover
  Then I review each carried flag and keep-apart before it applies
  And last year's observations stay on each pupil's record
```

---

## 7. Data and safety

### US-80 Nothing leaves my devices
**As** the teacher, **I want** the app reachable only from the laptop itself and my iPad over Tailscale, **so that** pupil data isn't exposed on the school network.
Must · Built (Phase 2)

```gherkin
Scenario: Not on the school network
  Given the server is running
  When another device on the school Wi-Fi tries the laptop's address
  Then it cannot connect
```

### US-81 Projector and cover show names only
**As** the class, and as a cover teacher, **we** see who sits where and nothing else.
Must · Built (Phase 1, step 9)

```gherkin
Scenario: The projector view
  Given pupils with flags, notes, groups and spoken-to marks
  When I open the projector view
  Then only seats, names and a "Front" marker are shown, black on white

Scenario: The cover PDF
  When I download the cover PDF
  Then it shows the room, the seats and names, and who is not seated
  And nothing about flags, notes, groups or attendance
```

### US-82 Nightly backups
**As** the teacher, **I want** the database copied every night to a folder I choose, **so that** a lost laptop doesn't lose a year.
Must · Built (hardening)

```gherkin
Scenario: A checked copy
  When the nightly backup runs
  Then a copy passes SQLite's integrity check
  And only the newest 30 copies are kept
```

### US-83 Export everything
**As** a pupil or parent, **I want** the teacher to be able to produce everything held, **so that** a subject access request can be answered.
Must · Built (hardening; the per-pupil export in Phase 5, step 5.5)

```gherkin
Scenario: Every table
  When I download everything
  Then the file contains every row of every Downbeat table
  And it loads back into an empty install

Scenario: One pupil, for a subject access request
  When I choose "Download everything held about Ada M" on her pupil page
  Then the file has every row that points at her, from every table, and the group feedback she was part of
  And no other pupil's name
```

### US-84 Delete everything
**As** the teacher, **I want** to wipe all data when I leave a school, **so that** nothing stays behind.
Must · Built (hardening)

```gherkin
Scenario: A deliberate act
  When I type "delete everything" and confirm
  Then every Downbeat row is gone, every device is signed out
  And the app returns to first-run setup
```

### US-85 Recordings only with permission
**As** a pupil or parent, **I want** recordings kept only with permission, reused only with separate permission, and deleted by the agreed date.
Must · Built (Phase 5, step 5.5)

```gherkin
Scenario: No permission, no recording
  Given Sam R does not have recording permitted
  Then no recording can be attached to Sam R's observations or feedback

Scenario: Past the delete-by date
  Given Aisha F's recordings were to be deleted by 25 October
  When I open Settings → Data
  Then her recordings' paths are listed under "Recordings"
  When I choose "Remove these references"
  Then Downbeat holds no reference to them and shows the paths once, for me to delete the files
```

### US-86 A clean install for another teacher
**As** another teacher, **I want** to install Downbeat and find nothing of anyone else's, **so that** I can use it for my own classes.
Should · Built (Phase 1; no values in migrations)

```gherkin
Scenario: Empty on install
  Given a new install
  Then there are no note types, flags, strands, bands or checklist items until I create them
```
