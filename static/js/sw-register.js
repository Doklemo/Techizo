/**
 * sw-register.js — Service Worker registration
 *
 * Registers the service worker from /static/sw.js if the browser supports it.
 * Logs success / failure to the console.
 */

(function () {
    "use strict";

    if ("serviceWorker" in navigator) {
        window.addEventListener("load", async () => {
            try {
                const registration = await navigator.serviceWorker.register(
                    "/sw.js",
                    { scope: "/" }
                );
                console.log("Techizo PWA: Service Worker registered. Scope:", registration.scope);

                // Listen for native Service Worker updates
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    if (newWorker) {
                        newWorker.addEventListener('statechange', () => {
                            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                // A new service worker has installed and is waiting
                                if (window.showToast) {
                                    window.showToast("New updates available — refresh");
                                }
                            }
                        });
                    }
                });
            } catch (err) {
                console.error("Techizo PWA: Service Worker registration failed:", err);
            }
        });
    }
})();
