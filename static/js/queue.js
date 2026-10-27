// Offline support: one file, two roles.
//   Registered at /sw.js it is the service worker: it keeps the app shell and the pages
//   already visited, so the iPad opens Downbeat with no connection.
//   Loaded by a page it registers that worker and holds every capture in IndexedDB until the
//   laptop confirms it, as window.downbeatQueue.
// The server fills in __CACHE_VERSION__ and the precache list when it serves /sw.js.

(() => {
  "use strict";

  const isWorker = typeof ServiceWorkerGlobalScope !== "undefined" && self instanceof ServiceWorkerGlobalScope;

  /* --- Service worker ------------------------------------------------------- */

  function worker() {
    const VERSION = "__CACHE_VERSION__";
    const PRECACHE = /*__PRECACHE__*/[];
    const SHELL = `downbeat-shell-${VERSION}`;
    const PAGES = "downbeat-pages"; // survives shell updates: the day's pages stay available
    const NETWORK_TIMEOUT = 4000; // ms before a slow school network gives way to the saved copy
    const NEVER_CACHE = ["/login/", "/logout/", "/sw.js", "/settings/data/"];
    const KEEP_PAGES_MS = 3 * 24 * 60 * 60 * 1000; // saved pages older than three days are dropped
    let lastPrune = 0;

    async function prunePages() {
      lastPrune = Date.now();
      const cache = await caches.open(PAGES);
      for (const request of await cache.keys()) {
        const response = await cache.match(request);
        const saved = Date.parse(response?.headers.get("Date") ?? "");
        if (!saved || Date.now() - saved > KEEP_PAGES_MS) await cache.delete(request);
      }
    }

    self.addEventListener("install", (event) => {
      event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
    });

    self.addEventListener("activate", (event) => {
      event.waitUntil(
        caches.keys()
          .then((keys) => Promise.all(keys.filter((k) => k.startsWith("downbeat-shell-") && k !== SHELL).map((k) => caches.delete(k))))
          .then(prunePages)
          .then(() => self.clients.claim()),
      );
    });

    self.addEventListener("message", (event) => {
      if (event.data === "clear") event.waitUntil(caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k)))));
    });

    const withTimeout = (promise, ms) =>
      Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), ms))]);

    async function shellFirst(request) {
      return (await caches.match(request)) ?? fetch(request);
    }

    async function networkFirst(request) {
      try {
        const response = await withTimeout(fetch(request), NETWORK_TIMEOUT);
        // Keep only real pages: a redirect usually means the session ended.
        if (response.ok && !response.redirected) {
          const cache = await caches.open(PAGES);
          await cache.put(request, response.clone());
          if (Date.now() - lastPrune > 60 * 60 * 1000) prunePages();
        }
        return response;
      } catch (error) {
        const saved = await caches.match(request);
        if (saved) return saved;
        if (request.mode === "navigate") return caches.match("/offline/");
        throw error;
      }
    }

    self.addEventListener("fetch", (event) => {
      const { request } = event;
      const url = new URL(request.url);
      if (request.method !== "GET" || url.origin !== self.location.origin) return;
      if (NEVER_CACHE.some((path) => url.pathname.startsWith(path))) return;
      event.respondWith(url.pathname.startsWith("/static/") ? shellFirst(request) : networkFirst(request));
    });
  }

  /* --- Page: the capture queue -------------------------------------------- */

  function page() {
    // iOS only allows service workers over HTTPS; the laptop's own localhost counts as secure.
    if ("serviceWorker" in navigator && window.isSecureContext) {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
    }

    // Signing out removes the saved pages, so nobody else can read the day's lessons offline.
    // Unsent captures stay: they belong to the teacher and go on the next sign-in.
    document.addEventListener("submit", (event) => {
      if (!event.target.matches("[data-sign-out]")) return;
      if ("caches" in window) caches.keys().then((keys) => keys.forEach((k) => caches.delete(k)));
    });

    window.downbeatQueue = createQueue();
  }

  /**
   * Every capture is an operation, kept in IndexedDB until the laptop confirms it, then sent to
   * /sync/ in the order it was made. Nothing is dropped unless the server says it is done with it.
   */
  /** A random UUID, made on the device so offline rows never clash with the laptop's. */
  function uuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  function createQueue() {
    const DB = "downbeat";
    const STORE = "ops";
    const BATCH = 200;
    const RETRY_MS = 20000;
    let flushing = null;
    let state = "idle"; // idle | sending | waiting (no connection) | signed-out
    let sequence = 0;
    let memory = []; // used only if IndexedDB is unavailable (some private modes)

    const database = new Promise((resolve) => {
      if (!("indexedDB" in window)) return resolve(null);
      const request = indexedDB.open(DB, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "op_id" });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(null);
    });

    async function run(mode, work) {
      const db = await database;
      if (!db) return work(null);
      return new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE, mode);
        const request = work(transaction.objectStore(STORE));
        transaction.oncomplete = () => resolve(request?.result);
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
      });
    }

    async function all() {
      const ops = (await run("readonly", (store) => (store ? store.getAll() : null))) ?? memory;
      return [...ops].sort((a, b) => a.seq - b.seq);
    }

    async function drop(ids) {
      const done = new Set(ids);
      memory = memory.filter((op) => !done.has(op.op_id));
      await run("readwrite", (store) => {
        if (store) for (const id of done) store.delete(id);
      });
    }

    async function announce() {
      const count = (await all()).length;
      document.dispatchEvent(new CustomEvent("downbeat:queue", { detail: { pending: count, state } }));
      return count;
    }

    function csrfToken() {
      return document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1] ?? "";
    }

    async function send() {
      for (;;) {
        const batch = (await all()).slice(0, BATCH);
        if (!batch.length) {
          state = "idle";
          return;
        }
        state = "sending";
        let response;
        try {
          response = await fetch("/sync/", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
            body: JSON.stringify({ ops: batch }),
          });
        } catch {
          state = "waiting";
          return;
        }
        if (response.status === 401 || response.status === 403) {
          state = "signed-out";
          return;
        }
        if (!response.ok) {
          state = "waiting";
          return;
        }
        const result = await response.json();
        const done = [...result.applied, ...result.rejected.map((r) => r.op_id)];
        await drop(done);
        for (const r of result.rejected) console.warn("Downbeat dropped a capture it can't apply:", r.reason);
        document.dispatchEvent(new CustomEvent("downbeat:synced", { detail: { done } }));
      }
    }

    function flush() {
      flushing ??= send().finally(() => {
        flushing = null;
        announce();
      });
      return flushing;
    }

    async function submit(op) {
      const entry = { op_id: uuid(), ...op, seq: Date.now() * 1000 + (sequence++ % 1000) };
      try {
        await run("readwrite", (store) => (store ? store.put(entry) : memory.push(entry)));
      } catch {
        memory.push(entry);
      }
      await announce();
      flush();
      return entry;
    }

    async function pending(session) {
      return (await all()).filter((op) => !session || op.session === session);
    }

    window.addEventListener("online", flush);
    document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && flush());
    setInterval(async () => {
      if ((await all()).length) flush();
    }, RETRY_MS);
    flush();

    return { submit, pending, flush, announce, uuid };
  }

  if (isWorker) worker();
  else page();
})();
