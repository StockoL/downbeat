// The seating canvas: free-placed seats, pointer-event drag, zones.
// One module for every page that draws a room. Each canvas declares its mode:
//   data-canvas="room"  room editor: move seats, paint zones, place the teacher
//   data-canvas="plan"  seating plan editor: drag pupils onto seats, swap, lock, bin, undo
//   data-canvas="view"  room view: taps become queued captures (queue.js); nothing moves; N = next lesson
//   data-canvas="projector"  names only, with a full-screen button
// Coordinates are canvas units (the room's width and height), never pixels.

const DRAG_THRESHOLD = 5; // pixels a press must travel before it counts as a drag
const SNAP = 10; // canvas units

function csrfToken() {
  const field = document.querySelector("[name=csrfmiddlewaretoken]");
  if (field) return field.value;
  return JSON.parse(document.body.getAttribute("hx-headers") || "{}")["X-CSRFToken"];
}

export async function post(url, data = {}) {
  const response = await fetch(url, {
    method: "POST",
    body: new URLSearchParams(data),
    headers: { "X-CSRFToken": csrfToken() },
  });
  if (!response.ok) throw new Error(`${url} answered ${response.status}`);
  return response.json();
}

const snap = (value) => Math.round(value / SNAP) * SNAP;
const clamp = (value, low, high) => Math.max(low, Math.min(value, high));

/**
 * Press, drag and release on elements matching `selector` inside `container`.
 * A press that never travels DRAG_THRESHOLD is a tap. `move` gets pixel deltas
 * and the element's canvas position when the press began.
 */
function onPress(container, selector, { tap, move, drop }) {
  container.addEventListener("pointerdown", (event) => {
    const el = event.target.closest(selector);
    if (!el || !container.contains(el) || event.button !== 0) return;
    event.preventDefault();
    const start = { x: event.clientX, y: event.clientY };
    const origin = { x: Number(el.dataset.x), y: Number(el.dataset.y) };
    let dragging = false;
    el.setPointerCapture(event.pointerId);

    const onMove = (e) => {
      const dx = e.clientX - start.x;
      const dy = e.clientY - start.y;
      if (!dragging && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
      if (!dragging) {
        dragging = true;
        el.classList.add("is-dragging");
      }
      move?.(el, dx, dy, origin, e);
    };
    const onUp = (e) => {
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
      el.classList.remove("is-dragging");
      if (e.type === "pointercancel") drop?.(el, e, true);
      else if (dragging) drop?.(el, e, false);
      else tap?.(el, e);
    };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
  });
}

/** Size and placement shared by every mode. */
class Canvas {
  constructor(root) {
    this.root = root;
    this.width = Number(root.dataset.width);
    this.height = Number(root.dataset.height);
    this.seatWidth = Number(root.dataset.seatWidth);
    this.seatHeight = Number(root.dataset.seatHeight);
  }

  /** Canvas units per screen pixel. */
  unitsPerPixel() {
    return this.width / this.root.getBoundingClientRect().width;
  }

  place(el, x, y) {
    el.dataset.x = x;
    el.dataset.y = y;
    el.style.setProperty("--x", x);
    el.style.setProperty("--y", y);
  }

  /** Drag an element across the canvas, snapped and kept inside the edges. */
  movable(selector, { size, save, tap }) {
    onPress(this.root, selector, {
      tap,
      move: (el, dx, dy, origin) => {
        const [w, h] = size(el);
        const scale = this.unitsPerPixel();
        const x = clamp(snap(origin.x + dx * scale), 0, this.width - w);
        const y = clamp(snap(origin.y + dy * scale), 0, this.height - h);
        this.place(el, x, y);
      },
      drop: (el) => save(el),
    });
  }
}

/* --- Room editor ---------------------------------------------------------- */

function initRoomEditor(root) {
  const canvas = new Canvas(root);
  const panel = document.getElementById("seat-panel");
  const labelInput = panel.querySelector("[name=label]");
  const brushes = document.getElementById("brushes");
  let selected = null;

  const brush = () => brushes.querySelector("input:checked")?.value ?? "move";
  const seatSize = () => [canvas.seatWidth, canvas.seatHeight];

  function render(seat, data) {
    seat.dataset.zone = data.zone;
    seat.dataset.near = data.near_teacher ? "true" : "false";
    seat.querySelector(".seat__name").textContent = data.label;
    const zoneName = brushes.querySelector(`input[value="${data.zone}"]`)?.dataset.label ?? "";
    seat.querySelector(".seat__meta").textContent = [zoneName, data.near_teacher ? "near teacher" : ""].filter(Boolean).join(" · ");
    seat.setAttribute("aria-label", `Seat ${data.label}${zoneName ? `, ${zoneName}` : ""}`);
  }

  function select(seat) {
    selected?.setAttribute("aria-pressed", "false");
    selected = seat;
    panel.hidden = !seat;
    if (!seat) return;
    seat.setAttribute("aria-pressed", "true");
    labelInput.value = seat.querySelector(".seat__name").textContent;
  }

  async function paint(seat) {
    const value = brush();
    const data = value === "near"
      ? { near_teacher: seat.dataset.near === "true" ? "0" : "1" }
      : { zone: value === "none" ? "" : value };
    render(seat, await post(seat.dataset.url, data));
  }

  const savePosition = async (seat) => render(seat, await post(seat.dataset.url, { x: seat.dataset.x, y: seat.dataset.y }));

  canvas.movable(".seat", {
    size: seatSize,
    save: async (seat) => {
      select(seat);
      await savePosition(seat);
    },
    tap: (seat) => (brush() === "move" ? select(seat) : paint(seat)),
  });

  canvas.movable(".teacher-marker", {
    size: () => [0, 0],
    save: (marker) => post(marker.dataset.url, { x: marker.dataset.x, y: marker.dataset.y }),
  });

  // Arrow keys nudge the focused seat, for anyone not using a pointer.
  root.addEventListener("keydown", async (event) => {
    const seat = event.target.closest(".seat");
    const step = { ArrowLeft: [-SNAP, 0], ArrowRight: [SNAP, 0], ArrowUp: [0, -SNAP], ArrowDown: [0, SNAP] }[event.key];
    if (!seat || !step) return;
    event.preventDefault();
    const x = clamp(Number(seat.dataset.x) + step[0], 0, canvas.width - canvas.seatWidth);
    const y = clamp(Number(seat.dataset.y) + step[1], 0, canvas.height - canvas.seatHeight);
    canvas.place(seat, x, y);
    await savePosition(seat);
  });

  labelInput.addEventListener("change", async () => {
    if (selected) render(selected, await post(selected.dataset.url, { label: labelInput.value }));
  });

  panel.querySelector("[data-action=delete]").addEventListener("click", async () => {
    if (!selected) return;
    await post(selected.dataset.deleteUrl);
    selected.remove();
    select(null);
  });

  panel.querySelector("[data-action=deselect]").addEventListener("click", () => select(null));
}

/* --- Seating plan editor -------------------------------------------------- */

// The server owns the plan: every drop, lock or undo posts and gets the board back
// re-rendered, so the page can never disagree with the database.
function initPlanEditor(wrapper) {
  let ghost = null;
  let over = null;

  async function send(url, data) {
    const response = await fetch(url, {
      method: "POST",
      body: new URLSearchParams(data),
      headers: { "X-CSRFToken": csrfToken() },
    });
    wrapper.innerHTML = await response.text();
  }

  const board = () => wrapper.querySelector(".plan-board");

  function target(event) {
    return document.elementFromPoint(event.clientX, event.clientY)?.closest("[data-drop]") ?? null;
  }

  function highlight(el) {
    if (over === el) return;
    over?.classList.remove("is-over");
    over = el;
    over?.classList.add("is-over");
  }

  onPress(wrapper, "[data-pupil]", {
    tap: (el) => {
      if (el.matches(".seat")) send(board().dataset.lockUrl, { seat: el.dataset.seat });
    },
    move: (el, dx, dy, origin, event) => {
      if (!ghost) {
        ghost = document.createElement("div");
        ghost.className = "drag-ghost";
        ghost.textContent = el.querySelector(".seat__name")?.textContent ?? el.textContent;
        document.body.append(ghost);
      }
      ghost.style.setProperty("--pointer-x", `${event.clientX}px`);
      ghost.style.setProperty("--pointer-y", `${event.clientY}px`);
      highlight(target(event));
    },
    drop: (el, event, cancelled) => {
      ghost?.remove();
      ghost = null;
      const drop = cancelled ? null : target(event);
      highlight(null);
      if (!drop || drop === el) return;
      const seat = drop.dataset.drop === "bin" ? "bin" : drop.dataset.seat;
      if (seat === "bin" && !el.matches(".seat")) return; // already unseated
      send(board().dataset.moveUrl, { pupil: el.dataset.pupil, seat });
    },
  });

  wrapper.addEventListener("click", (event) => {
    if (event.target.closest("[data-action=undo]")) send(board().dataset.undoUrl);
    if (event.target.closest("[data-action=shuffle]")) send(board().dataset.shuffleUrl);
  });
}

/* --- Room view ------------------------------------------------------------ */

// The lesson as data. `base` is what the laptop last said; the device's unsent captures are
// replayed on top, so the room looks the same with or without a connection. Every tap becomes
// an operation for the queue (queue.js), which sends it when the laptop is in reach.

const UNDO_LIMIT = 10;
const STATE_WORDS = { not_yet: "not yet", partly: "partly", secure: "secure" };
const LONG_PRESS_MS = 500;
const ICON_FREE_TEXT = "✎";

function el(tag, attributes = {}, text = "") {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  if (text) node.textContent = text;
  return node;
}

/** Apply one capture to a lesson state. The same rules run for fresh taps and replayed ones. */
function applyOp(s, op, graveyard) {
  const noteType = (id) => s.noteTypes.find((t) => t.id === id);
  switch (op.type) {
    case "note.add": {
      if (s.notes.some((n) => n.id === op.id)) break;
      const type = noteType(op.note_type);
      const note = {
        id: op.id, pupil: op.pupil ?? null, group: op.group ?? null, type: op.note_type ?? null, text: op.text ?? "",
        actionable: type ? type.actionable : Boolean(op.actionable), done: false, at: op.at,
      };
      s.notes.push(note);
      if (note.actionable) s.actions.push({ ...note, when: "Today" });
      break;
    }
    case "note.remove": {
      const note = s.notes.find((n) => n.id === op.note);
      if (note) graveyard.set(note.id, note);
      s.notes = s.notes.filter((n) => n.id !== op.note);
      s.actions = s.actions.filter((n) => n.id !== op.note);
      break;
    }
    case "note.restore": {
      const note = graveyard.get(op.note);
      if (!note || s.notes.some((n) => n.id === note.id)) break;
      s.notes.push(note);
      if (note.actionable && !note.done) s.actions.push({ ...note, when: "Today" });
      break;
    }
    case "action.done":
      s.actions = s.actions.filter((n) => n.id !== op.note);
      for (const n of s.notes) if (n.id === op.note) n.done = true;
      break;
    case "spoken.add":
      s.spoken[op.pupil] = [...(s.spoken[op.pupil] ?? []).filter((id) => id !== op.id), op.id];
      break;
    case "spoken.remove":
      for (const pupil of Object.keys(s.spoken)) s.spoken[pupil] = s.spoken[pupil].filter((id) => id !== op.spoken);
      break;
    case "spoken.clear":
      s.spoken[op.pupil] = [];
      break;
    case "attendance.set":
      s.absent = s.absent.filter((id) => id !== op.pupil);
      s.present = s.present.filter((id) => id !== op.pupil);
      (op.present ? s.present : s.absent).push(op.pupil);
      break;
    case "checklist.tick":
      s.ticked[op.item] = [...(s.ticked[op.item] ?? []), op.id];
      break;
    case "checklist.untick":
      s.ticked[op.item] = [];
      break;
    case "observation.add":
      if (!s.observations.some((o) => o.id === op.id)) {
        s.observations.push({ id: op.id, pupil: op.pupil, component: op.component, state: op.state, nextStep: op.next_step, at: op.at });
      }
      break;
    case "observation.update":
      for (const o of s.observations) if (o.id === op.observation) o.nextStep = op.next_step;
      break;
    case "observation.remove":
      s.observations = s.observations.filter((o) => o.id !== op.observation);
      break;
  }
}

function initRoomView(root) {
  const queue = window.downbeatQueue;
  const sheet = document.getElementById("sheet");
  const body = document.getElementById("sheet-body");
  const log = document.getElementById("log");
  const undoButton = document.querySelector("[data-action=undo]");
  const syncStatus = document.querySelector("[data-sync-status]");
  let base = JSON.parse(document.getElementById("lesson-state").textContent);
  const session = base.session;
  let pending = [];
  const graveyard = new Map(); // removed notes, so undo can bring them back before the laptop confirms
  const undoKey = `downbeat-undo:${session}`;
  let picker = { whole: false, last: null };

  /* State ---------------------------------------------------------------- */

  function view() {
    const s = structuredClone(base);
    for (const op of pending) applyOp(s, op, graveyard);
    return s;
  }

  const typeOf = (s, note) => s.noteTypes.find((t) => t.id === note.type);
  const iconOf = (s, note) => typeOf(s, note)?.icon || ICON_FREE_TEXT;
  const labelOf = (s, note) => typeOf(s, note)?.label ?? note.text;
  const nameOf = (s, pupil) => s.pupils.find((p) => p.id === pupil)?.name ?? "Class";
  const groupNameOf = (s, group) => s.groups.find((g) => g.id === group)?.name ?? "Group";
  const whoOf = (s, note) => (note.group ? groupNameOf(s, note.group) : nameOf(s, note.pupil));
  const isSpoken = (s, pupil) => (s.spoken[pupil] ?? []).length > 0;
  const unread = (s, pupil) => (s.elsewhere[pupil] ?? 0) + s.actions.filter((n) => n.pupil === pupil).length;
  const byTime = (a, b) => a.at.localeCompare(b.at);
  const isTicked = (s, item) => (s.ticked[item] ?? []).length > 0;
  const componentText = (s, id) => s.components.find((c) => c.id === id)?.text ?? "Component";
  const ticked = (s) => s.checklist.filter((item) => isTicked(s, item.id)).length;
  const describe = (s, note) => `${iconOf(s, note)} ${labelOf(s, note)}${note.type && note.text ? `: ${note.text}` : ""}`;

  const saving = new Set(); // captures not yet written to the queue

  function submit(op) {
    const entry = { ...op, op_id: queue.uuid(), session, at: new Date().toISOString() };
    pending.push(entry);
    saving.add(entry.op_id);
    render();
    return queue.submit(entry).finally(() => saving.delete(entry.op_id));
  }

  /**
   * After a sync: take the laptop's state, then replay only what it hasn't confirmed, which is
   * whatever is still in the queue or still being written to it.
   */
  async function refresh() {
    try {
      const response = await fetch(root.dataset.stateUrl, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!response.ok || response.redirected) return;
      base = await response.json();
    } catch {
      return; // can't see the new state yet; the next sync will try again
    }
    const queued = new Set((await queue.pending(session)).map((op) => op.op_id));
    pending = pending.filter((op) => queued.has(op.op_id) || saving.has(op.op_id));
    render();
  }

  /* Undo: the last ten note adds and removes, kept as their opposite operations. */

  function undoStack() {
    try {
      return JSON.parse(sessionStorage.getItem(undoKey) ?? "[]");
    } catch {
      return [];
    }
  }

  function saveUndo(stack) {
    try {
      sessionStorage.setItem(undoKey, JSON.stringify(stack.slice(-UNDO_LIMIT)));
    } catch {
      // Storage blocked: undo is a convenience, the capture itself is safe.
    }
  }

  /* Drawing ---------------------------------------------------------------- */

  function render() {
    const s = view();
    const absent = new Set(s.absent);
    const missed = new Set(s.missed);
    const out = new Set(s.out);

    for (const marks of document.querySelectorAll("[data-marks]")) {
      const pupil = marks.dataset.marks;
      marks.toggleAttribute("data-spoken", isSpoken(s, pupil));
      marks.toggleAttribute("data-absent", absent.has(pupil));
      marks.toggleAttribute("data-missed", missed.has(pupil));
      marks.toggleAttribute("data-out", out.has(pupil));
      const icons = s.notes.filter((n) => n.pupil === pupil).sort(byTime).map((n) => iconOf(s, n)).join("");
      const count = unread(s, pupil);
      const children = [];
      if (icons) children.push(el("span", { class: "seat__badges", "aria-hidden": "true" }, icons));
      if (count) children.push(el("span", { class: "seat__unread", "aria-label": `${count} open` }, String(count)));
      if (out.has(pupil)) children.push(el("span", { class: "visually-hidden" }, "at an instrumental lesson"));
      else if (absent.has(pupil)) children.push(el("span", { class: "visually-hidden" }, "absent"));
      else if (isSpoken(s, pupil)) children.push(el("span", { class: "visually-hidden" }, "spoken to"));
      marks.replaceChildren(...children);
    }

    for (const marks of document.querySelectorAll("[data-marks-group]")) {
      const group = marks.dataset.marksGroup;
      const icons = s.notes.filter((n) => n.group === group).sort(byTime).map((n) => iconOf(s, n)).join("");
      marks.replaceChildren(...(icons ? [el("span", { class: "seat__badges", "aria-hidden": "true" }, icons)] : []));
    }

    // Notes and observations together, in the order they were caught.
    const entries = [
      ...s.notes.map((note) => ({
        at: note.at, text: `${whoOf(s, note)} · ${describe(s, note)}`, label: labelOf(s, note), who: whoOf(s, note),
        remove: { "data-action": "remove", "data-note": note.id },
      })),
      ...s.observations.map((o) => ({
        at: o.at, text: `${nameOf(s, o.pupil)} · ${componentText(s, o.component)}: ${STATE_WORDS[o.state]}`,
        label: componentText(s, o.component), who: nameOf(s, o.pupil),
        remove: { "data-action": "remove-observation", "data-observation": o.id },
      })),
    ].sort(byTime);
    log.replaceChildren(...entries.map((entry) => {
      const line = el("li", { class: "room-log__line" });
      const time = new Date(entry.at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
      line.append(
        el("span", { class: "room-log__time" }, time),
        el("span", {}, entry.text),
        el("button", {
          type: "button", class: "button room-log__remove", "data-variant": "ghost", ...entry.remove,
          "aria-label": `Remove ${entry.label} for ${entry.who}`,
        }, "✕"),
      );
      return line;
    }));

    document.querySelector("[data-actions-count]").textContent = s.actions.length || "";
    renderStrip(s);

    // Goals: lessons with at least one note of the type, this one included once it has one.
    const goalsSlot = document.querySelector("[data-goals]");
    if (goalsSlot) {
      goalsSlot.replaceChildren(...s.goals.map((goal) => {
        const count = goal.others + (s.notes.some((n) => n.type === goal.noteType) ? 1 : 0);
        return el("span", { class: "room-bar__goal", "aria-label": `${goal.label}: ${count} of ${goal.target}` },
          `${goal.icon} ${count}/${goal.target}`);
      }));
    }
    const registerCount = document.querySelector("[data-register-count]");
    if (registerCount) registerCount.textContent = `${s.present.length}/${s.pupils.length}`;
    const checklistCount = document.querySelector("[data-checklist-count]");
    if (checklistCount) checklistCount.textContent = `${ticked(s)}/${s.checklist.length}`;
    undoButton.hidden = undoStack().length === 0;
    if (sheet.open && body.dataset.sheet === "actions") fillActions(s);
    if (sheet.open && body.dataset.sheet === "checklist") fillChecklist(s);
    if (sheet.open && body.dataset.sheet === "register") fillRegister(s);
  }

  /* The panel: Log or Plan, with the strip summarising whichever isn't showing. ---------- */

  const strip = document.querySelector("[data-strip]");
  const logPanel = document.getElementById("log-panel");
  const planPanel = document.getElementById("plan-panel");
  let showingPlan = false;

  /** Where the lesson has got to by the clock: the activity now, from the period's start and the minutes. */
  function whereWeAre(plan, now = Date.now()) {
    if (!plan?.start || !plan.activities.length) return null;
    const elapsed = Math.floor((now - Date.parse(plan.start)) / 60000);
    if (elapsed < 0) return { before: true, elapsed, index: 0 };
    let total = 0;
    for (const [index, activity] of plan.activities.entries()) {
      total += activity.minutes;
      if (elapsed < total) return { index, elapsed };
    }
    return { index: plan.activities.length - 1, elapsed, over: true };
  }

  function renderStrip(s) {
    if (!strip) return;
    const plan = s.plan;
    const at = whereWeAre(plan);
    if (showingPlan) {
      const last = [...s.notes].sort(byTime).at(-1);
      strip.textContent = last ? `Log: ${whoOf(s, last)} · ${describe(s, last)}` : "Log";
      strip.setAttribute("aria-label", "Show the log");
    } else {
      const now = at && plan.activities[at.index];
      const next = at && plan.activities[at.index + 1];
      if (!at) {
        strip.textContent = plan.carried.length
          ? `Carried forward: ${plan.carried.map((c) => c.text).join(", ")}`
          : plan.objective;
      }
      else if (at.before) strip.textContent = `First: ${now.text}`;
      else strip.textContent = [`Now: ${now.text} · ${at.elapsed} min in`, next ? `Next: ${next.text}` : ""].filter(Boolean).join("  ·  ");
      strip.setAttribute("aria-label", `${strip.textContent}. Show the plan`);
    }
    for (const item of planPanel?.querySelectorAll("[data-activity]") ?? []) {
      const current = at && !at.before && plan.activities[at.index]?.id === item.dataset.activity;
      if (current) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    }
  }

  function flip() {
    if (!planPanel) return;
    showingPlan = !showingPlan;
    planPanel.hidden = !showingPlan;
    logPanel.hidden = showingPlan;
    renderStrip(view());
  }

  if (strip) setInterval(() => renderStrip(view()), 30000);

  /* Sheets ----------------------------------------------------------------- */

  function show(templateId, kind) {
    body.replaceChildren(document.getElementById(templateId).content.cloneNode(true));
    body.dataset.sheet = kind;
    if (!sheet.open) sheet.showModal();
  }

  function close() {
    if (sheet.open) sheet.close();
  }

  /** Who the open sheet's notes are for: a pupil or a group. */
  function subject() {
    return body.dataset.group ? { group: body.dataset.group } : { pupil: body.dataset.pupil };
  }

  function openNoteSheet(pupil) {
    const s = view();
    show("tpl-note-sheet", "note");
    delete body.dataset.group;
    body.dataset.pupil = pupil;
    body.querySelector("[data-slot=name]").textContent = nameOf(s, pupil);
    body.querySelector("[data-action=spoken]").setAttribute("aria-pressed", String(isSpoken(s, pupil)));
    body.querySelector("[data-action=absent]").setAttribute("aria-pressed", String(s.absent.includes(pupil)));
    const count = unread(s, pupil);
    const counter = body.querySelector("[data-action=inbox]");
    counter.hidden = !count;
    counter.textContent = count;
    counter.setAttribute("aria-label", `${count} open note${count === 1 ? "" : "s"} for ${nameOf(s, pupil)}`);
    body.querySelector("[data-slot=badges]").textContent =
      s.notes.filter((n) => n.pupil === pupil).sort(byTime).map((n) => iconOf(s, n)).join(" ");
    body.querySelector("[data-action=observe-sheet]").hidden = !s.components.length;
  }

  /** This unit's components, three states each. A tap saves with the default next step attached. */
  function openObservationSheet(pupil) {
    const s = view();
    if (!s.components.length) {
      openNoteSheet(pupil);
      return;
    }
    show("tpl-observation", "observe");
    delete body.dataset.group;
    delete body.dataset.observation;
    body.dataset.pupil = pupil;
    body.querySelector("[data-slot=name]").textContent = nameOf(s, pupil);
    fillObservations(s);
  }

  function fillObservations(s) {
    const pupil = body.dataset.pupil;
    const latest = {};
    for (const o of [...s.observations].sort(byTime)) if (o.pupil === pupil) latest[o.component] = o.state;
    body.querySelector("[data-slot=list]").replaceChildren(...s.components.map((component) => {
      const row = el("li", { class: "observe__row" });
      const states = el("div", { class: "observe__states" });
      for (const [state, words] of Object.entries(STATE_WORDS)) {
        states.append(el("button", {
          type: "button", class: "button", "data-action": "observe", "data-component": component.id, "data-state": state,
          "aria-pressed": String(latest[component.id] === state),
        }, words[0].toUpperCase() + words.slice(1)));
      }
      row.append(el("span", {}, component.text), states);
      return row;
    }));
  }

  /** A group's sheet: the same note buttons, without spoken to, absent or the inbox. */
  function openGroupSheet(group) {
    const s = view();
    show("tpl-note-sheet", "note");
    delete body.dataset.pupil;
    body.dataset.group = group;
    body.querySelector("[data-slot=name]").textContent = groupNameOf(s, group);
    body.querySelector(".note-sheet__toggles").hidden = true;
    body.querySelector("[data-action=inbox]").hidden = true;
    body.querySelector("[data-slot=badges]").textContent =
      s.notes.filter((n) => n.group === group).sort(byTime).map((n) => iconOf(s, n)).join(" ");
  }

  function openFreeText() {
    const s = view();
    const who = subject();
    show("tpl-free-text", "free-text");
    body.querySelector("[data-slot=name]").textContent = who.group ? groupNameOf(s, who.group) : nameOf(s, who.pupil);
    body.querySelector("textarea").focus();
  }

  async function openInbox(pupil) {
    try {
      const response = await fetch(`/room/${session}/inbox/${pupil}/`, { credentials: "same-origin" });
      if (!response.ok || response.redirected) throw new Error("unavailable");
      body.innerHTML = await response.text(); // the laptop's own template; it escapes names and text
      body.dataset.sheet = "inbox";
    } catch {
      show("tpl-offline", "offline");
      body.querySelector("[data-slot=name]").textContent = nameOf(view(), pupil);
    }
  }

  function fillActions(s) {
    const list = body.querySelector("[data-slot=list]");
    if (!s.actions.length) {
      list.replaceChildren(el("li", { class: "sheet-list__when" }, "Nothing open."));
      return;
    }
    list.replaceChildren(...s.actions.map((note) => {
      const item = el("li", { class: "cluster" });
      item.append(
        el("span", { class: "sheet-list__when" }, note.when),
        el("span", { class: "sheet-list__what" }, `${whoOf(s, note)} · ${describe(s, note)}`),
        el("button", { type: "button", class: "button", "data-action": "done", "data-note": note.id }, "Done"),
      );
      return item;
    }));
  }

  function fillChecklist(s) {
    body.querySelector("[data-slot=list]").replaceChildren(...s.checklist.map((item) => {
      const button = el("button", {
        type: "button", class: "button checklist__item", "data-size": "large",
        "data-action": "tick", "data-item": item.id, "aria-pressed": String(isTicked(s, item.id)),
      }, item.text);
      const row = el("li");
      row.append(button);
      return row;
    }));
  }

  /** The ensemble register: each member present, absent or not yet marked. */
  function fillRegister(s) {
    const present = new Set(s.present);
    const absent = new Set(s.absent);
    body.querySelector("[data-slot=list]").replaceChildren(...s.pupils.map((pupil) => {
      const state = present.has(pupil.id) ? "present" : absent.has(pupil.id) ? "absent" : "unmarked";
      const button = el("button", {
        type: "button", class: "button register__pupil", "data-action": "mark", "data-pupil-id": pupil.id,
        "data-state": state, "aria-label": `${pupil.name}: ${state === "unmarked" ? "not marked" : state}`,
      }, pupil.name);
      const row = el("li");
      row.append(button);
      return row;
    }));
  }

  function openRegister() {
    show("tpl-register", "register");
    fillRegister(view());
  }

  function openChecklist() {
    show("tpl-checklist", "checklist");
    fillChecklist(view());
  }

  function openActions() {
    show("tpl-actions", "actions");
    fillActions(view());
  }

  function draw() {
    const s = view();
    const away = new Set([...s.absent, ...s.out]); // absent, or at an instrumental lesson
    const present = s.pupils.filter((p) => !away.has(p.id));
    let pool = picker.whole ? present : present.filter((p) => !isSpoken(s, p.id));
    if (!pool.length) pool = present; // everyone has had a turn: start again
    const pupil = pool.length ? pool[Math.floor(Math.random() * pool.length)] : null;
    picker.last = pupil ? { pupil: pupil.id, spoken: queue.uuid() } : null;
    if (pupil) submit({ type: "spoken.add", id: picker.last.spoken, pupil: pupil.id });

    if (body.dataset.sheet !== "picker" || !sheet.open) show("tpl-picker", "picker");
    body.querySelector("[data-slot=name]").textContent = pupil ? pupil.name : "No one to pick";
    body.querySelector(".picker__hint").hidden = !pupil;
    const poolButton = body.querySelector("[data-action=pool]");
    poolButton.textContent = picker.whole ? "Whole class" : "Not yet spoken to";
    poolButton.setAttribute("aria-pressed", String(picker.whole));
    const absentButton = body.querySelector("[data-action=picked-absent]");
    absentButton.hidden = !pupil;
    if (pupil) absentButton.textContent = `${pupil.name.split(" ")[0]} is absent`;
  }

  /* Taps --------------------------------------------------------------------- */

  function addNote(fields) {
    const id = queue.uuid();
    submit({ type: "note.add", id, ...subject(), ...fields });
    saveUndo([...undoStack(), { type: "note.remove", note: id }]);
    close();
  }

  // A long-press on a seat opens the observation sheet; the click that follows it is swallowed.
  let pressTimer = null;
  let longPressed = false;
  document.addEventListener("pointerdown", (event) => {
    const seat = event.target.closest(".seat[data-pupil]");
    if (!seat || !base.components.length) return;
    const start = { x: event.clientX, y: event.clientY };
    longPressed = false;
    const cancel = () => clearTimeout(pressTimer);
    pressTimer = setTimeout(() => {
      longPressed = true;
      openObservationSheet(seat.dataset.pupil);
    }, LONG_PRESS_MS);
    seat.addEventListener("pointerup", cancel, { once: true });
    seat.addEventListener("pointercancel", cancel, { once: true });
    seat.addEventListener("pointermove", (e) => {
      if (Math.hypot(e.clientX - start.x, e.clientY - start.y) > 8) cancel();
    });
  });
  document.addEventListener("contextmenu", (event) => {
    if (event.target.closest(".seat[data-pupil]")) event.preventDefault();
  });

  document.addEventListener("click", (event) => {
    if (longPressed) {
      longPressed = false;
      if (event.target.closest(".seat[data-pupil]")) return;
    }
    const target = event.target.closest("[data-action], [data-pupil], [data-group], [data-close-sheet]");
    if (!target) return;
    if (target.matches("[data-close-sheet]")) {
      close();
      return;
    }
    const pupil = body.dataset.pupil;
    switch (target.dataset.action) {
      case undefined:
        if (target.matches(".seat[data-pupil]")) openNoteSheet(target.dataset.pupil);
        else if (target.matches(".seat[data-group]")) openGroupSheet(target.dataset.group);
        break;
      case "note": {
        const type = base.noteTypes.find((t) => t.id === target.dataset.noteType);
        addNote({ note_type: type.id, text: "", actionable: type.actionable });
        break;
      }
      case "free-text":
        openFreeText();
        break;
      case "observe-sheet":
        openObservationSheet(pupil);
        break;
      case "observe": {
        const component = base.components.find((c) => c.id === target.dataset.component);
        const id = queue.uuid();
        submit({ type: "observation.add", id, pupil, component: component.id, state: target.dataset.state, next_step: component.nextStep });
        body.dataset.observation = id;
        fillObservations(view());
        body.querySelector("[data-slot=step]").textContent = component.nextStep;
        body.querySelector("[data-slot=confirm]").hidden = false;
        body.querySelector("[data-form=next-step]").hidden = true;
        break;
      }
      case "change-step": {
        const form = body.querySelector("[data-form=next-step]");
        form.hidden = false;
        form.querySelector("input").value = body.querySelector("[data-slot=step]").textContent;
        form.querySelector("input").focus();
        break;
      }
      case "remove-observation":
        submit({ type: "observation.remove", observation: target.dataset.observation });
        break;
      case "spoken":
        submit(isSpoken(view(), pupil) ? { type: "spoken.clear", pupil } : { type: "spoken.add", id: queue.uuid(), pupil });
        close();
        break;
      case "absent":
        submit({ type: "attendance.set", pupil, present: view().absent.includes(pupil) });
        close();
        break;
      case "inbox":
        openInbox(pupil);
        break;
      case "back":
        openNoteSheet(target.dataset.pupil);
        break;
      case "remove":
        submit({ type: "note.remove", note: target.dataset.note });
        saveUndo([...undoStack(), { type: "note.restore", note: target.dataset.note }]);
        render();
        break;
      case "undo": {
        const stack = undoStack();
        const op = stack.pop();
        saveUndo(stack);
        if (op) submit(op);
        else render();
        break;
      }
      case "actions":
        openActions();
        break;
      case "checklist":
        openChecklist();
        break;
      case "register":
        openRegister();
        break;
      case "mark": {
        // Unmarked or absent → present; present → absent.
        const pupilId = target.dataset.pupilId;
        submit({ type: "attendance.set", pupil: pupilId, present: target.dataset.state !== "present" });
        break;
      }
      case "all-present": {
        const s = view();
        const marked = new Set([...s.present, ...s.absent]);
        for (const pupil of s.pupils) {
          if (!marked.has(pupil.id)) submit({ type: "attendance.set", pupil: pupil.id, present: true });
        }
        break;
      }
      case "tick": {
        const item = target.dataset.item;
        submit(isTicked(view(), item) ? { type: "checklist.untick", item } : { type: "checklist.tick", id: queue.uuid(), item });
        break;
      }
      case "shortcuts":
        show("tpl-shortcuts", "shortcuts");
        break;
      case "flip":
        flip();
        break;
      case "done":
        submit({ type: "action.done", note: target.dataset.note });
        break;
      case "pick":
        picker = { whole: false, last: null };
        draw();
        break;
      case "draw":
        draw();
        break;
      case "pool":
        picker.whole = !picker.whole;
        draw();
        break;
      case "picked-absent": {
        if (!picker.last) break;
        const { pupil: away, spoken } = picker.last;
        submit({ type: "spoken.remove", spoken });
        submit({ type: "attendance.set", pupil: away, present: false });
        draw();
        break;
      }
    }
  });

  document.addEventListener("submit", (event) => {
    if (event.target.matches("[data-form=next-step]")) {
      event.preventDefault();
      const nextStep = String(new FormData(event.target).get("next_step") ?? "").trim();
      if (nextStep && body.dataset.observation) {
        submit({ type: "observation.update", observation: body.dataset.observation, next_step: nextStep });
        body.querySelector("[data-slot=step]").textContent = nextStep;
        event.target.hidden = true;
      }
      return;
    }
    if (!event.target.matches("[data-form=free-text]")) return;
    event.preventDefault();
    const form = new FormData(event.target);
    const text = String(form.get("text") ?? "").trim();
    if (text) addNote({ note_type: null, text, actionable: form.get("actionable") === "on" });
    else close();
  });

  sheet.addEventListener("click", (event) => {
    if (event.target === sheet) close(); // the backdrop
  });
  sheet.addEventListener("close", () => {
    body.replaceChildren();
    delete body.dataset.sheet;
    delete body.dataset.pupil;
    delete body.dataset.group;
    delete body.dataset.observation;
  });

  document.addEventListener("downbeat:synced", refresh);
  document.addEventListener("downbeat:queue", (event) => {
    const { pending: count, state } = event.detail;
    if (!count) syncStatus.textContent = "";
    else if (state === "signed-out") syncStatus.textContent = `Sign in to send ${count}`;
    else syncStatus.textContent = `${count} saved on this device`;
  });

  /* The panel: a side column at desk width, a sheet docked above the bar when narrower.
     Its handle opens and closes it with a tap, a key press or a swipe. */

  const panel = document.getElementById("lesson-panel");
  const handle = panel.querySelector(".room-layout__handle");
  let swiped = false;

  function setPanel(open) {
    panel.dataset.state = open ? "open" : "closed";
    handle.setAttribute("aria-expanded", String(open));
    handle.setAttribute("aria-label", open ? "Hide the log" : "Show the log");
  }

  handle.addEventListener("click", () => {
    if (swiped) swiped = false; // the click that ends a swipe has already been handled
    else setPanel(panel.dataset.state !== "open");
  });
  onPress(panel, ".room-layout__handle", {
    drop: (el, event, cancelled) => {
      if (cancelled) return;
      swiped = true;
      setTimeout(() => (swiped = false), 100); // in case the browser sends no click after the swipe
      const rise = el.getBoundingClientRect().top - event.clientY; // positive when dragged up
      if (Math.abs(rise) > 20) setPanel(rise > 0);
    },
  });

  /* Keys, for the laptop. None of them fire while typing. */

  const KEYS = {
    n: () => root.dataset.nextUrl && window.location.assign(root.dataset.nextUrl),
    p: () => document.querySelector("[data-action=pick]").click(),
    a: () => document.querySelector("[data-action=actions]").click(),
    u: () => undoButton.hidden || undoButton.click(),
    l: () => setPanel(panel.dataset.state !== "open"),
    "?": () => show("tpl-shortcuts", "shortcuts"),
  };
  const SHEET_KEYS = { s: "spoken", x: "absent", f: "free-text", o: "observe-sheet" };

  document.addEventListener("keydown", (event) => {
    // Tab flips Log and Plan, but only when nothing has focus, so keyboard navigation still works.
    if (event.key === "Tab" && !event.shiftKey && planPanel && !sheet.open && document.activeElement === document.body) {
      event.preventDefault();
      flip();
      return;
    }
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.target.closest("input, textarea, select, [contenteditable]")) return;
    const key = event.key.toLowerCase();
    if (sheet.open) {
      if (body.dataset.sheet !== "note") return;
      const target = /^[1-9]$/.test(key)
        ? body.querySelectorAll("[data-action=note]")[Number(key) - 1]
        : SHEET_KEYS[key] && body.querySelector(`[data-action="${SHEET_KEYS[key]}"]`);
      if (target && !target.closest("[hidden]")) {
        event.preventDefault();
        target.click();
      }
      return;
    }
    if (KEYS[key]) {
      event.preventDefault();
      KEYS[key]();
    }
  });

  // The page itself may be a saved copy from earlier in the lesson: draw it with this device's
  // queue on top straight away, then take the newest state (the laptop's, or the newest saved one).
  queue.pending(session).then((ops) => {
    pending = ops;
    render();
    queue.announce();
    refresh();
  });
}

/* --- Projector ------------------------------------------------------------ */

function initProjector(stage) {
  stage.querySelector("[data-action=fullscreen]")?.addEventListener("click", () => {
    stage.requestFullscreen?.();
  });
}

const modes = { room: initRoomEditor, plan: initPlanEditor, view: initRoomView, projector: initProjector };

for (const root of document.querySelectorAll("[data-canvas]")) {
  modes[root.dataset.canvas]?.(root);
}
