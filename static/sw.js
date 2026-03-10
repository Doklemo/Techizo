importScripts('https://storage.googleapis.com/workbox-cdn/releases/7.0.0/workbox-sw.js');

if (workbox) {
    console.log(`Techizo PWA: Workbox 7.0 loaded successfully. ✨`);

    // ── Precaching ──────────────────────────────────────────────────────────
    // Precaches critical shell assets statically.
    workbox.precaching.precacheAndRoute([
        { url: '/', revision: '3' },
        { url: '/static/css/tokens.css', revision: '3' },
        { url: '/static/css/base.css', revision: '3' },
        { url: '/static/css/components.css', revision: '3' },
        { url: '/static/css/dark.css', revision: '3' },
        { url: '/static/js/app.js', revision: '3' },
        { url: '/static/js/theme.js', revision: '3' },
        { url: '/static/js/sw-register.js', revision: '3' },
        { url: '/static/manifest.json', revision: '3' },
        { url: '/static/icons/icon-192.png', revision: '3' },
        { url: '/static/icons/icon-512.png', revision: '3' }
    ]);

    // ── Static Assets Strategy ──────────────────────────────────────────────
    workbox.routing.registerRoute(
        /\.(?:css|js|png|svg)$/,
        new workbox.strategies.CacheFirst({
            cacheName: 'pulse-static-v1',
            plugins: [
                new workbox.expiration.ExpirationPlugin({
                    maxEntries: 50,
                })
            ]
        })
    );

    // ── API Feed Strategy ───────────────────────────────────────────────────
    workbox.routing.registerRoute(
        new RegExp('/api/feed'),
        new workbox.strategies.NetworkFirst({
            cacheName: 'pulse-feed-v1',
            networkTimeoutSeconds: 5,
            plugins: [
                new workbox.expiration.ExpirationPlugin({
                    maxAgeSeconds: 2 * 60 * 60, // 2 hours
                })
            ]
        })
    );

} else {
    console.warn(`Techizo PWA: Workbox failed to load. 😬`);
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
