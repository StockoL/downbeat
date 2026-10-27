// The seating canvas: free-placed seats, pointer-event drag, zones.
// One module for every page that draws a room. Each canvas declares its mode:
//   data-canvas="room"  room editor: move seats, paint zones, place the teacher
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

  /**
   * Press, drag and release on elements matching `selector`.
   * A press that never travels DRAG_THRESHOLD is a tap. `move` gets canvas-unit deltas
   * and the element's position when the press began.
   */
  onDrag(selector, { tap, move, drop }) {
    this.root.addEventListener("pointerdown", (event) => {
      const el = event.target.closest(selector);
      if (!el || !this.root.contains(el) || event.button !== 0) return;
      event.preventDefault();
      const start = { x: event.clientX, y: event.clientY };
      const origin = { x: Number(el.dataset.x), y: Number(el.dataset.y) };
      const scale = this.unitsPerPixel();
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
        move?.(el, dx * scale, dy * scale, origin, e);
      };
      const onUp = (e) => {
        el.removeEventListener("pointermove", onMove);
        el.removeEventListener("pointerup", onUp);
        el.removeEventListener("pointercancel", onUp);
        el.classList.remove("is-dragging");
        if (e.type === "pointercancel") return;
        if (dragging) drop?.(el, e);
        else tap?.(el, e);
      };
      el.addEventListener("pointermove", onMove);
      el.addEventListener("pointerup", onUp);
      el.addEventListener("pointercancel", onUp);
    });
  }

  /** Drag an element across the canvas, snapped and kept inside the edges. */
  movable(selector, { size, save, tap }) {
    this.onDrag(selector, {
      tap,
      move: (el, dx, dy, origin) => {
        const [w, h] = size(el);
        this.place(el, clamp(snap(origin.x + dx), 0, this.width - w), clamp(snap(origin.y + dy), 0, this.height - h));
      },
      drop: save,
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

const modes = { room: initRoomEditor };

for (const root of document.querySelectorAll("[data-canvas]")) {
  modes[root.dataset.canvas]?.(root);
}
