/**
 * theme.js — Dark / Light mode toggle
 *
 * Reads preference from localStorage (light, dark).
 * Exposes window.setThemePreference to dynamically update theme and UI.
 */

(function () {
    "use strict";

    const STORAGE_KEY = "pulse-theme";
    const DARK = "dark";
    const LIGHT = "light";

    /**
     * Determine the stored preference: "dark" or "light" (default).
     */
    function getStoredPreference() {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored === DARK || stored === LIGHT) {
            return stored;
        }
        return LIGHT; // Default to the true light theme
    }

    /**
     * Apply the given theme (dark/light) to the document.
     */
    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
    }

    /**
     * Syncs the Appearance tabs in the Settings UI to match the current preference.
     */
    function updateUI(preference) {
        const tabs = document.querySelectorAll('.settings-tab');
        if (!tabs.length) return;

        tabs.forEach(tab => {
            if (tab.getAttribute('data-theme-val') === preference) {
                tab.classList.add('is-active');
            } else {
                tab.classList.remove('is-active');
            }
        });
    }

    /**
     * Expose global function to change theme from Settings page.
     * @param {"dark" | "light"} preference 
     */
    window.setThemePreference = function (preference) {
        if (![DARK, LIGHT].includes(preference)) return;

        localStorage.setItem(STORAGE_KEY, preference);
        applyTheme(preference);
        updateUI(preference);
    };

    // ── Initialise ──────────────────────────────────────────────────
    const initialPref = getStoredPreference();
    applyTheme(initialPref);

    // Update UI when DOM is ready
    document.addEventListener("DOMContentLoaded", () => {
        updateUI(initialPref);
    });

})();
