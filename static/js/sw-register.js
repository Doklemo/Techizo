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
                console.log(
                    "Service Worker registered — scope:",
                    registration.scope
                );
            } catch (err) {
                console.error("Service Worker registration failed:", err);
            }
        });
    }
})();
