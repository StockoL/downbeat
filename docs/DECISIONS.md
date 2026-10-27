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
