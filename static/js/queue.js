// Offline support: one file, two roles.
//   Registered at /sw.js it is the service worker: it keeps the app shell and the pages
//   already visited, so the iPad opens Downbeat with no connection.
//   Loaded by a page it registers that worker (and, from Phase 2's queue, holds captures in
//   IndexedDB until the laptop is reachable).
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

  /* --- Page ----------------------------------------------------------------- */

  function page() {
    // iOS only allows service workers over HTTPS; the laptop's own localhost counts as secure.
    if ("serviceWorker" in navigator && window.isSecureContext) {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
    }

    // Signing out removes the saved pages, so nobody else can read the day's lessons offline.
    document.addEventListener("submit", (event) => {
      if (!event.target.matches("[data-sign-out]")) return;
      if ("caches" in window) caches.keys().then((keys) => keys.forEach((k) => caches.delete(k)));
    });
  }

  if (isWorker) worker();
  else page();
})();
