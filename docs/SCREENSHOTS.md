# Screenshots

Evidence of the user journeys and key features, captured from the demo school. Every pupil in the demo is invented (first name and initial, generated from a fixed seed), so no real pupil data appears here.

Captured on 28 October 2026 at the end of Phase 6, in Microsoft Edge. Laptop shots are 1440 × 900; iPad shots are 820 × 1180, an iPad Air in portrait. The room view shots were taken with the browser's clock at 10:17, inside 9Y's P2 lesson. To capture them again after a change, run `.venv\Scripts\python tools\screenshots.py` (see [DEVELOPMENT.md](DEVELOPMENT.md#screenshots)).

Story numbers (US-nn) refer to [USER_STORIES.md](USER_STORIES.md), and journeys are those in [UX.md](UX.md#user-journeys).

## Contents

- [Journey: walk in and teach](#journey-walk-in-and-teach)
- [Journey: catch an observation](#journey-catch-an-observation)
- [Journey: hinge moment](#journey-hinge-moment)
- [Journey: next lesson](#journey-next-lesson)
- [Journey: day's end sweep](#journey-days-end-sweep)
- [Journey: plan next week](#journey-plan-next-week)
- [Journey: reshuffle a class](#journey-reshuffle-a-class)
- [Pupils](#pupils)
- [Setting up and looking after the data](#setting-up-and-looking-after-the-data)
- [Rules made visible](#rules-made-visible)
- [Still to come](#still-to-come)

---

## Journey: walk in and teach

*Open the app → the current lesson's room → tap a seat → tap a note. Two taps per note, none to reach the room.* (US-10, US-11)

**Today.** Outside a lesson, the day's sessions are listed in period order, with the choir rehearsal marked co-curricular and "♪ 1 out" for a pupil at an instrumental lesson (US-25). During a lesson, opening the app skips this list and goes straight to the room.

![Today: the day's lessons in period order](screenshots/03-today.png)

**The room view on the laptop.** The canvas is on the left and the Log on the right. Seats show this lesson's badges (★ house point, ✓ great answer), coloured flag edges (US-35), group tints (US-36), the dot for an open action (US-15), and a thicker edge for pupils missed last lesson (US-18). Spoken-to seats are dimmed, and an absent pupil is struck through (US-20). The bottom bar has the goal counter, the checklist "✓ 0/3" and Actions (US-23), then Pick, Hinge (US-17) and Next.

![Room view at laptop width with the Log](screenshots/04-room-view-laptop.png)

**The room view on the iPad.** The same room with the panel docked as a sheet below. The strip reads "Now: Riffs on keyboards: in pairs · 27 min in · Next: Share and feedback" (US-22).

![Room view at iPad width with the docked panel](screenshots/23-ipad-room-view.png)

**Tap a seat.** The note sheet rises over the room without hiding it: Spoken to and Absent at the top, then the teacher's own note types, house point first and free text last. Tapping one records the note and closes the sheet.

![The note sheet over the room](screenshots/24-ipad-note-sheet.png)

**Plan or Log.** Tapping the strip flips the panel to the lesson plan, with the current activity highlighted; the strip then shows the last Log line.

![The plan side of the panel](screenshots/05-room-view-plan-panel.png)

**The picker** draws a present pupil not yet spoken to, and records the turn (US-19). **Actions** lists open actions carried from earlier lessons with the class (US-15). **The checklist** is the lesson's routine, ticked through the queue.

| Picker | Actions | Checklist |
| --- | --- | --- |
| ![The random picker](screenshots/27-ipad-picker.png) | ![Open actions](screenshots/28-ipad-actions.png) | ![The lesson checklist](screenshots/29-ipad-checklist.png) |

**With the Wi-Fi off.** Two house points recorded offline appear in the Log and on the seats at once. The bar says "2 saved on this device" in plain text until the laptop is reachable (US-12).

![Captures saved on the device while offline](screenshots/30-ipad-offline-log.png)

**Dark mode** for a dimmed room with the projector on.

![Room view in dark mode](screenshots/22-room-view-dark.png)

## Journey: catch an observation

*Long-press a seat → this unit's components → tap a state → the next step attaches. Two taps after the long-press.* (US-16, US-38)

| Long-press opens the components | One tap saves it with the default next step |
| --- | --- |
| ![The observation sheet](screenshots/25-ipad-observation-sheet.png) | ![The next step attached, with Change](screenshots/26-ipad-observation-next-step.png) |

The saved observation joins the Log in time order with the notes ("Dev M · Plays a riff in time with the band: secure" in the offline shot above).

## Journey: hinge moment

*Hinge button → the question, the answers and a timer → tap a decision. Two taps.* (US-17, US-42)

The sheet is full height: the question large, the right answer marked, each wrong answer with the misconception it shows (on the teacher's screen only), the threshold, and a timer running since it opened. One tap on Re-taught, Moved on or Paired records the decision for the class and closes the sheet. No pupil's answer is recorded (rule 3).

![The hinge check sheet](screenshots/32-ipad-hinge-check.png)

The decision then shows on the bar as "Hinge · moved on" and in the Log, as in the offline shot above. On a lesson whose plan has no check, the button stays in its place, greyed.

## Journey: next lesson

*Room view → Next → the next session's room. One tap.* (US-21)

The bar's "Next: P5 · 10 GCSE ›" button is in every room view shot above; N does the same on the laptop.

## Journey: day's end sweep

*Sweep → a session → statuses, caught notes, reflection → carry-forward → Prep.* (US-50 to US-56)

**The day's sessions** as cards, with the first unswept one outlined; a swept session gets a tick.

![Sweep: a day's sessions](screenshots/13-sweep-day.png)

**A session's sweep** is one scroll. First, each activity's status, with "If unfinished, carry to …" ticked by default. Then the caught notes, each with a Bin tick. Then the hinge check, to record the decision from memory if it wasn't made in the room (US-53); this unit opts in to pupils' answers, so "Each pupil's answer" opens a table of the class (US-57). Last, one reflection line, with Teachers' Standards tags and "Turn this into a goal".

![One session's sweep](screenshots/14-session-sweep.png)

**Prep for tomorrow**, generated from the plans' resources and the open actions, with ticks that persist (US-52).

![Prep for the next teaching day](screenshots/15-prep.png)

**Feedback for a lesson**, from "Feedback for this lesson" at the top of its sweep or in the room view's ⋯ menu; the pupil page has its own "Write feedback" too (US-62). Done well, to develop and how, for a pupil or a group, optionally against a component. A recording is a path and a moment in it ("at 1:42"), and only for pupils whose families agreed.

![A lesson's feedback page](screenshots/33-lesson-feedback.png)

## Journey: plan next week

*Plan → class → unit → lesson → activities, components, resources.* (US-34, US-37, US-38, US-40)

| Classes | A class's lessons |
| --- | --- |
| ![Plan: classes](screenshots/09-plan-classes.png) | ![A class's sessions with their lessons](screenshots/10-class-lessons.png) |

**The lesson editor**: objective, activities with minutes, resources with print flags, and the hinge check with each wrong answer's misconception.

![The lesson editor](screenshots/12-lesson-editor.png)

**A unit's Assessment tab**: pupil-facing components, each with a strand and default next step, feedback codes, the criteria file to download or import, the unit's bank of hinge checks, and its exemplars at three levels, one of them a pupil's whose family agreed to its reuse (US-41).

![Unit components and feedback codes](screenshots/11-unit-components.png)

**The feedback codes as a slide** (US-43), opened in its own window from the Assessment tab, a lesson's feedback page or the room's ⋯ menu: large type, black on white, nothing about any pupil.

![Feedback codes as a slide](screenshots/37-feedback-codes-slide.png)

## Journey: reshuffle a class

*Plan → class → seating → drag with validation lines → lock → shuffle.* (US-30 to US-33, US-39)

The summary reads "1 keep-apart pair side by side. 3 seats not meeting a flag's seating rule." A red line joins the keep-apart pair, and dotted outlines mark the seats breaking a flag rule. Shuffle keeps locked pupils in place and never seats a keep-apart pair together.

![The seating editor with validation lines](screenshots/07-seating-editor.png)

**The room editor** (Settings → Rooms): seats placed freely, zones painted, the teacher position marked (US-04).

![The room editor](screenshots/08-room-editor.png)

## Pupils

**A class list** with flag swatches but no labels (US-35).

![A class in the Pupils area](screenshots/16-class-pupils.png)

**The pupil page** is the one place a flag's label, its note and "what works" appear (US-60). Relationships and notes sit beside them.

![A pupil's page](screenshots/17-pupil-page.png)

Further down the page, **their feedback and observations**, then **recordings over time** (US-66): each recording in order, one line per component, with what was heard or said then. A pupil is compared only with their own earlier work. The page also offers "Download everything held about …" for a subject access request (US-83).

![A pupil's feedback and observations](screenshots/36-pupil-feedback-and-observations.png)

**The class by component** (US-63): each pupil's latest state on each of a unit's components, in words, greyscale only (an outline for not yet, a shade for partly, solid for secure). Teacher, self and peer are shown separately. Nothing is added up.

![The class-by-component view](screenshots/34-class-components.png)

**Self and peer in one go** (US-64): a lesson, a component, self or peer, then each pupil's answer. Each is kept with the component's next step.

![Self- and peer-assessment entry](screenshots/35-self-and-peer.png)

| Missing out (US-61) | Loans (US-65) |
| --- | --- |
| ![Missing out: fewest first, plain counts](screenshots/18-missing-out.png) | ![The equipment loan log](screenshots/19-loans.png) |

**Judgements** (US-70): a band per strand of a unit, with each pupil's latest state on the strand's components above the choice. Every choice starts at "Not judged": nothing is suggested.

![The judgement grid](screenshots/38-class-judgements.png)

**Reports** (US-71, US-72): each pupil's comment drafted from their bands and the comment bank, then their latest feedback, with the count against the school's limit, Save, Copy and Draft again. The whole class downloads as CSV.

![The class's reports](screenshots/39-class-reports.png)

**Settings → Reports**: the house style (the character limit and the third-person check) and the comment bank.

![Report settings](screenshots/40-report-settings.png)

**A parents' evening** (US-74): its times from the start, end, slot length and break, who is booked, booking a family, and the school's booking file.

![A parents' evening](screenshots/41-parents-evening.png)

| Booking from the class list: two taps | On the night, on the iPad |
| --- | --- |
| ![Booking a family](screenshots/42-ipad-book-a-family.png) | ![The night's list](screenshots/43-ipad-parents-evening-night.png) |

**The ensemble register** for a choir rehearsal (US-24).

![The choir register](screenshots/31-ipad-ensemble-register.png)

## Setting up and looking after the data

**First-run setup on an empty install** (US-01, US-86): the account, timetable, note types, a first room, and optional flags and checklist, with nothing pre-filled.

![First-run setup](screenshots/01-first-run-setup.png)

| Sign in (US-05) | Settings |
| --- | --- |
| ![Sign in](screenshots/02-sign-in.png) | ![Settings](screenshots/20-settings.png) |

**Settings → Data**: back up now, download everything, recordings that may no longer be kept (here one past its pupil's delete-by date) with "Remove these references" (US-85), and delete everything behind a typed phrase (US-82 to US-84).

![Settings → Data](screenshots/21-data.png)

## Rules made visible

| Rule (BUILD_ORDER) | Where to see it |
| --- | --- |
| 1. Capture is two taps, never a form | Note sheet, observation sheet, hinge sheet |
| 2. A lesson with no input has no nags | The room view bar: plain counts, no colour, no prompts |
| 3. Whole-class checks store the decision | The hinge sheet records a decision, never votes; pupils' answers only in the sweep, for a unit that opts in |
| 4. An observation carries a next step | "Next step: Lock in with the drummer's snare" attached on the first tap |
| 5. No progress arithmetic | The class-by-component view: states in words, no totals, averages or percentages |
| 8. Flags are colour only | Seats show coloured edges; the label appears only on the pupil page |
| 9. Projector and cover show names only | The projector view below: seats and names, black on white, no badges, flags, groups, dimming or absence |
| 10. First name and initial | Every name in every shot |

![The projector-safe view](screenshots/06-projector-view.png)

## Still to come

Every journey in UX.md now has its screens. Still to come is the rollover before the second September, which is a job rather than a journey.
