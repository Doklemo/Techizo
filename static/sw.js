/**
 * sw.js — Pulse Service Worker
 *
 * Strategy:
 *   • App-shell assets → cache-first (fast repeat loads)
 *   • API calls        → network-first (fresh data, offline fallback)
 *
 * The cache is versioned; bumping CACHE_VERSION will purge old caches.
 */

const CACHE_VERSION = "pulse-v40";

// Assets that form the installable app shell
const APP_SHELL = [
    "/",
    "/static/css/tokens.css",
    "/static/css/base.css",
    "/static/css/components.css",
    "/static/css/dark.css",
    "/static/js/app.js",
    "/static/js/theme.js",
    "/static/js/sw-register.js",
    "/static/manifest.json",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png",
];

// ── Install: pre-cache the app shell ──────────────────────────────
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL))
    );
    // Activate immediately without waiting for old tabs
    self.skipWaiting();
});

// ── Activate: purge outdated caches ───────────────────────────────
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => key !== CACHE_VERSION)
                    .map((key) => caches.delete(key))
            )
        )
    );
    // Claim all open clients immediately
    self.clients.claim();
});

// ── Fetch: strategy depends on request type ───────────────────────
self.addEventListener("fetch", (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // API requests → network-first w/ cache fallback
    if (url.pathname.startsWith("/api/")) {
        event.respondWith(networkFirst(request));
        return;
    }

    // JS and CSS → network-first so code updates always arrive
    if (url.pathname.endsWith(".js") || url.pathname.endsWith(".css")) {
        event.respondWith(networkFirst(request));
        return;
    }

    // Everything else (icons, manifest, HTML) → cache-first
    event.respondWith(cacheFirst(request));
});

/**
 * Cache-first: return cached response if available, else fetch and cache.
 * @param {Request} request
 * @returns {Promise<Response>}
 */
async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) return cached;

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_VERSION);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        // Offline and not cached — return a basic fallback
        return new Response("Offline", {
            status: 503,
            statusText: "Service Unavailable",
        });
    }
}

/**
 * Network-first: try network, fall back to cache on failure.
 * @param {Request} request
 * @returns {Promise<Response>}
 */
async function networkFirst(request) {
    try {
        const response = await fetch(request);
        // Cache successful API responses for offline use
        if (response.ok) {
            const cache = await caches.open(CACHE_VERSION);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        const cached = await caches.match(request);
        if (cached) return cached;

        // Return empty array for API fallback
        return new Response("[]", {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });
    }
}

// ── Web Push Notifications ────────────────────────────────────────
self.addEventListener("push", function (event) {
    if (event.data) {
        try {
            const payload = event.data.json();
            const options = {
                body: payload.body,
                icon: payload.icon || "/static/icons/icon-192.png",
                vibrate: [100, 50, 100],
                data: { url: payload.url || "/" },
            };
            event.waitUntil(
                self.registration.showNotification(payload.title, options)
            );
        } catch (e) {
            console.error("Push event payload parse error:", e);
        }
    }
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
            for (let client of windowClients) {
                if (client.url.includes(event.notification.data.url) && "focus" in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(event.notification.data.url);
            }
        })
    );
});
