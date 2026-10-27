# Downbeat: UX decisions

27 October 2026.

Companion to BUILD_ORDER.md. Written as Garrett's five planes, bottom up: strategy and scope are inherited from the build doc, structure and skeleton are where the decisions are, surface is deferred.

## Strategy and scope

One user, the teacher, on two devices: an iPad in the hand while circulating, a laptop at the desk and sometimes at the front. The need is to hold the frame for each lesson and catch the residue of what happened, without the app ever asking for attention during the lesson itself. Success is behavioural, not functional: five taps a lesson and a two-minute sweep still happening in March, and the paper seating plan not having been printed since October.

Scope is the build-order doc. The UX decision scope adds is subtractive: the in-room surface shows plan, log and the room, and nothing else. Curriculum, reports, pupils' histories, settings, exemplars, goals beyond the live tally, all of it is reachable only from the desk tempos. A feature that wants to be on the room screen has to displace one of the three things already there.

## Structure

The top level is the three tempos plus the people they are about: Today, Sweep, Plan, Pupils, and a settings gear. It is not the data model. A teacher who sees Pupils, Classes, Rooms, Units, Observations and Reports as navigation is looking at the tables and will hunt for things mid-lesson. Everything else is reached from a session or from a pupil.

Page map:

| Today (catch: in the room) | Sweep (desk, same day) | Plan (desk, ahead) | Pupils (desk, any time) |
| --- | --- | --- | --- |
| Sessions list | Today's sessions | Classes | Class list, pupil page |
| Room view | Activity statuses | Units and lessons | Judgement grid |
| Note sheet | Confirm caught notes | Components, codes | Report export |
| Observation sheet | Reflection, carry-forwards | Exemplars | Parents' evenings |
| Hinge check | Prep for tomorrow | Seating editor, groups | Loans |

Settings (gear): timetable, rooms, note types, flags, strands, bands, rotation import, backup, rollover, first-run setup.

Today is the only area used in the room; the other three are desk work. Prep lives inside Sweep because they happen at the same desk at the same hour. Curriculum, units, components and exemplars live inside Plan because they are set before a lesson. Judgements, reports, parents' evenings and loans live inside Pupils because that is whose data they are. Settings holds everything configured once, including the first-run setup and the September rollover.

Where a feature lives, when it is not obvious from the map: the weekly goal tally and the per-lesson checklist appear as counters in the room view's bottom bar and are edited from Settings; the random picker is a button in the room view and writes to spoken-to; the "missing out" check and the class-by-component heat view are tabs on a class inside Pupils; the Rotation (who is out for an instrumental lesson) is imported in Settings and surfaces only as a grey seat; the cover PDF and projector view are actions on the room view's overflow menu, never on the main bar.

## User journeys

Eight journeys cover the app. The tap budget is the design constraint: the first three happen with a class in the room and must stay inside it; the rest are desk work and can take as long as the task needs.

| Journey | Path | Budget |
| --- | --- | --- |
| Walk in and teach | Open app → Today lands on current session → room view → tap seat → note sheet, tap one of five buttons → back to room | 2 taps per note; 0 to reach the room |
| Catch an observation | Room view → long-press seat → component list for this unit → tap state → next step attaches, back to room | 2 taps after the long-press |
| Hinge moment | Room view → hinge button → question and timer shown → tap decision (re-taught / moved on / paired) → back to room | 2 taps |
| Next lesson | Room view → chevron or N key → next session's room | 1 tap |
| Day's end sweep | Sweep → today's sessions → one session: activity statuses, caught notes to confirm or bin, voice notes, class-level hinge judgement, reflection line → carry-forward prompts → Prep for tomorrow | Two minutes per session |
| Plan next week | Plan → class → unit → lesson slot → structured form: activities, components in play, resources with print flags → save | Desk, unbounded |
| Reshuffle a class | Plan → class → seating → drag with validation lines, lock seats, shuffle button → save | Desk, unbounded |
| Report season | Pupils → class → judgement grid → per pupil: band per strand with evidence beside it → assemble sentences → copy with counter | Desk, unbounded |
| Parents' evening | Pupils → evenings → tonight → tap slot → pupil page → mark attended or not | 2 taps per family |

The first journey is the one the whole app is judged by. If reaching the room view from a cold open takes more than one screen, or logging a house point takes a third tap, the app has failed its own rule and the fix is to remove something, not to add a shortcut.

## Page inventory

Fifteen pages and five modals. Modals are sheets over the room view and never navigate away from it; the room stays visible behind them.

| Page | Area | Kind | Layout notes |
| --- | --- | --- | --- |
| Today | Today | page | Today's sessions in time order, current one expanded; co-curricular sessions inline. Skipped on open if a session is live |
| Room view | Today | page | The seating canvas plus panel and bottom bar; the home screen for a lesson |
| Note sheet | Today | modal | Five or six big buttons, badges along the top, unread counter on the name |
| Observation sheet | Today | modal | This unit's components, three states each, next step shown after the tap |
| Hinge check | Today | modal | Question, distractors, timer, three decision buttons |
| Picker | Today | modal | One name, large; tap to draw again; writes spoken-to |
| Inbox | Today | modal | Pupil's notes newest first; reached only from the counter |
| Sweep | Sweep | page | Today's sessions as cards with a done tick; opens the first unswept |
| Session sweep | Sweep | page | Activities with status toggles, caught items to confirm, hinge judgement, reflection, carry-forward prompts |
| Prep | Sweep | page | Tomorrow's sessions with generated and manual items to tick |
| Plan: classes | Plan | page | Class cards with current unit and next lesson |
| Class | Plan | page | Tabs: lessons, seating, groups |
| Lesson editor | Plan | page | Structured form; activities as a reorderable list; resources with print flag |
| Unit editor | Plan | page | Components, feedback codes, exemplars, purpose field |
| Room editor | Plan | page | Canvas: place seats, paint zones, mark the teacher position |
| Pupils: classes | Pupils | page | Class cards; tabs per class for list, judgement grid, heat view, missing-out |
| Pupil page | Pupils | page | Flags with labels, instrument, timeline of recordings, notes, observations, judgements |
| Report export | Pupils | page | Per pupil: assembled text, counter, copy; whole-class CSV |
| Parents' evening | Pupils | page | Slot list for tonight; tap opens pupil page in a sheet with attended toggle |
| Settings | Settings | page | Timetable, rooms, note types, flags, strands, bands, checklist, goals, rotation import, backup, rollover, first-run setup |

## Skeleton

One template, two layouts. On the laptop the canvas takes the left two-thirds and the panel the right third. On the iPad, portrait or landscape, the canvas takes the full width and the panel is a swipe-up sheet; the laptop layout is reserved for a real desktop width (a container-query breakpoint around 1024px, never a device check), since small tablets can't afford a side panel. The bottom bar is identical on both: session name, house-point tally, checklist count, open-action count, the picker, the hinge button and next-session. Checklist and actions open as sheets from their counters; they never get a tab.

Room view, laptop layout:

```
+--------------------------------------------------+------------------------------+
| Room canvas (free-placed seats, zones)           | [Now: riff in pairs · 12 min]|
|                                                  | [Next: swap parts · tap=Plan]|
|  [    ] [    ] [    ] [    ]        [    ]       | Log                          |
|  [    ] [Aleya K•] [    ] [    ]    [    ]       | 10:12 Aleya K · house point  |
|                                      [    ]      | 10:15 Group 3 · no structure |
|  [    ] [    ] [    ] [    ]                     | 10:19 Jojo P · swing: partly |
|                  teacher position                | 10:21 hinge · moved on       |
+--------------------------------------------------+------------------------------+
| P3 · 8X Mu · Blues L4    HP 7/20   ✓ 2/4   ! 3   pick   HINGE            next › |
+---------------------------------------------------------------------------------+
```

The panel is only ever one of two things, Log or Plan. It opens on Log, because by the time the lesson has started the plan is a glance, not a read. What you are not looking at is summarised in a strip at the top of the panel: when Log is showing, the strip is the current activity, the next one and minutes elapsed; when Plan is showing, the strip is the last log line. Tapping the strip flips the panel; on the laptop the Tab key does the same. There is no tab row, because a row of four tabs puts the two used mid-lesson next to two that aren't.

The seat is the component the whole app hangs on, and it has to carry six states on roughly 80 by 44 pixels without text. First name and initial in the middle. A coloured left edge for flags, one colour per flag type, stacked as thin bands if a pupil has more than one. A small dot top-right with an unread count when there are notes in the inbox. Dimmed to 50 per cent when spoken to this lesson. A background tint when the pupil is in a group, one tint per group. Greyed with a strike when out for an instrumental lesson this period. Highlighted with a thicker edge when the pupil is on the "didn't get to last time" list. States combine, so the design test is a flagged, grouped, unread, unspoken-to pupil still reading as one calm rectangle; if it doesn't, drop the group tint first.

Tap a seat and the note sheet rises over the room without hiding it: badges this pupil already has along the top as small icons, the unread counter on their name, then five or six large buttons from the teacher's note types, house point first, free text last. Nothing from past notes is shown. Tapping the counter slides the inbox over the sheet; otherwise no past note is ever read during a lesson. Long-press opens the observation sheet instead: this unit's components as rows, three state buttons each, and after a tap the default next step appears as a confirmation line, editable with one more tap but never required.

The hinge check is a full-height sheet: the question large, the distractors with their misconception tags visible only to the teacher, a timer that starts on open, and three decision buttons at the bottom. Nothing in it records per pupil unless the opt-in is turned on in the unit.

The desk pages use an ordinary two-column layout with the LooseLeaf-UI `.sidebar` composition: list on the left, detail on the right, no modals. The session sweep is the one desk page with a tempo of its own and is laid out as a single scroll: activities with three-state toggles, then caught items as a checklist to keep or bin, then the hinge judgement, then one reflection line, then the carry-forward prompts, so the whole thing reads top to bottom in the two minutes it is allowed.

## Surface

Deferred until Phase 1 is in use, with four constraints fixed now because they are hard to retrofit. Nothing tappable in the room view is under 44 by 44 points. Flag colours are a reserved palette of six to eight hues used nowhere else in the interface, so a blue button never sits beside a blue flag edge; interface chrome stays greyscale with one accent that is not in the flag set. Type in the room view is a size up from the desk pages, since it is read at arm's length while walking. Dark mode exists from the start because the room view will be on in a dimmed room with a projector running, and the projector-safe view is high-contrast black on white regardless of theme. Typography, spacing scales and components come from LooseLeaf-UI; this doc does not restate them.

## Decisions

Settled 27 Oct 2026: navigation is by tempo (Today, Sweep, Plan, Pupils, Settings), never by table. The room view panel defaults to Log, with the plan reduced to a current-and-next strip; the strip is the flip between the two and there is no tab row. Checklist and actions are counters in the bottom bar that open sheets. The note sheet shows existing badges and an unread counter only; past notes are behind the counter, never on the sheet. The seat carries six visual states without text and group tint is the first to go if they clash. Modals never leave the room view. Desk pages are list-and-detail with no modals. The session sweep is a single scroll.

Also settled: the hinge button is always on the bar, greyed when the plan has no Check, so its position never moves. iPad landscape is the portrait layout with a wider canvas, not the laptop layout, because small tablets can't afford a panel. The picker draws from the not-yet-spoken-to by default, with a toggle to the whole class. Prep is a tab inside Sweep on every device.
