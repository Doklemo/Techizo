/**
 * app.js — Pulse Newspaper Page-Flip Feed
 *
 * Cards are stacked via z-index.  The top card flips like a
 * newspaper page (hinged on the left edge) when the user
 * swipes horizontally.
 *
 * Gesture handling uses raw mouse + touch events (no Pointer API)
 * for maximum browser compatibility.
 *
 * Bookmark / Save feature uses localStorage key 'pulse-saved'.
 */

(function () {
    "use strict";

    // ── Constants ────────────────────────────────────────────────────
    const STORAGE_KEY = "pulse-saved";
    const BOOKMARK_OUTLINE = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>`;
    const BOOKMARK_FILLED = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>`;

    // ── DOM References ──────────────────────────────────────────────
    const swipeWrapper = document.getElementById("swipe-wrapper");
    const todayDateEl = document.getElementById("today-date");
    const savedBadge = document.getElementById("saved-badge");
    const feedContainer = document.getElementById("feed-container");
    const footerAction = document.getElementById("footer-action");
    const navPrev = document.getElementById("nav-prev");
    const navNext = document.getElementById("nav-next");
    const toast = document.createElement("div");
    toast.className = "toast";
    document.body.appendChild(toast);

    // ── State ───────────────────────────────────────────────────────
    let allArticles = [];
    let currentIndex = 0;
    let cardEls = [];
    let currentView = "feed";
    let feedIndex = 0;

    // Gesture state
    let tracking = false;  // finger/mouse is down
    let dragging = false;  // past the dead-zone, actually swiping
    let isAnimating = false; // blocks interaction during flips
    let startX = 0;
    let flipProgress = 0;
    const DEAD_ZONE = 10;       // px before we consider it a swipe
    const FLIP_THRESHOLD = 0.3; // 30% to complete flip
    const MAX_DRAG_PX = 200;    // px for a full flip

    // ── Bootstrap ───────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", () => {
        setTodayDate();
        updateSavedBadge();
        loadFeed();
    });

    // ── UI Helpers ──────────────────────────────────────────────────
    function setTodayDate() {
        const today = new Date();
        const options = { month: "short", day: "numeric" };
        if (todayDateEl) {
            todayDateEl.textContent = today.toLocaleDateString("en-US", options);
        }
    }

    function showToast(message, duration = 3000) {
        toast.textContent = message;
        toast.classList.add("is-visible");
        setTimeout(() => toast.classList.remove("is-visible"), duration);
    }

    // ── localStorage Helpers ────────────────────────────────────────
    function getSavedArticles() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (err) {
            console.error("Failed to read saved articles:", err);
            return [];
        }
    }

    function saveArticlesToStorage(articles) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(articles));
        } catch (err) {
            console.error("Failed to save articles:", err);
        }
    }

    function isArticleSaved(url) {
        return getSavedArticles().some((a) => a.url === url);
    }

    function toggleSaveArticle(article) {
        let saved = getSavedArticles();
        const idx = saved.findIndex((a) => a.url === article.url);

        if (idx >= 0) {
            saved.splice(idx, 1);
            showToast("Removed from saved");
        } else {
            saved.unshift(article);
            showToast("Saved for later");
        }

        saveArticlesToStorage(saved);
        updateSavedBadge();
        return idx < 0; // returns true if now saved
    }

    function updateSavedBadge() {
        const count = getSavedArticles().length;
        if (savedBadge) {
            savedBadge.textContent = count > 0 ? count : "";
            savedBadge.setAttribute("data-count", count);
        }
    }

    // ── Feed Loading ────────────────────────────────────────────────
    async function loadFeed() {
        showSkeletons(3);

        try {
            const res = await fetch("/api/feed");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            allArticles = await res.json();

            if (allArticles.length === 0) {
                showEmpty("No news for today.");
            } else {
                renderArticles(allArticles);
                attachGestures();
            }
        } catch (err) {
            console.error("Failed to load feed:", err);
            showEmpty("Something went wrong. Please try again.");
        }
    }

    // ── Rendering ───────────────────────────────────────────────────
    function renderArticles(articles) {
        swipeWrapper.innerHTML = "";
        const total = articles.length;
        cardEls = [];
        currentIndex = 0;

        articles.forEach((article, index) => {
            const snapContainer = document.createElement("article");
            snapContainer.className = "snap-card";
            snapContainer.style.zIndex = total - index;

            let domain = "example.com";
            try { domain = new URL(article.url).hostname; } catch (e) { }

            let logoHtml = `<img class="card__source-logo" src="https://www.google.com/s2/favicons?domain=${domain}&sz=32" alt="">`;
            let sourceName = escapeHtml(article.source);

            if (article.title.toLowerCase().includes("anthropic") || article.summary.toLowerCase().includes("anthropic")) {
                logoHtml = `<svg class="card__source-logo" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L22 20H17L12 11L7 20H2L12 2Z"/></svg>`;
                sourceName = "Anthropic";
            }

            const isSaved = isArticleSaved(article.url);
            const bookmarkClass = isSaved ? "card__bookmark card__bookmark--saved" : "card__bookmark";
            const bookmarkIcon = isSaved ? BOOKMARK_FILLED : BOOKMARK_OUTLINE;

            snapContainer.innerHTML = `
                <div class="card">
                    <button class="${bookmarkClass}" data-url="${escapeHtml(article.url)}" aria-label="Save article">
                        ${bookmarkIcon}
                    </button>

                    <div class="card__pagination">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                        ${index + 1}/${total}
                    </div>
                    
                    <div class="card__content">
                        <div class="card__source">
                            ${logoHtml}
                            <span class="card__source-name">${sourceName}</span>
                        </div>
                        <h2 class="card__title">${escapeHtml(article.title)}</h2>
                        <p class="card__summary">${escapeHtml(article.summary)}</p>
                    </div>

                    <div class="card__footer">
                        <a href="${escapeHtml(article.url)}" class="btn-read" target="_blank" rel="noopener noreferrer">
                            Read full news
                        </a>
                    </div>
                </div>

                <div class="card-back">
                    <div class="card-back__inner"></div>
                </div>
            `;

            // Wire up the bookmark button
            const bookmarkBtn = snapContainer.querySelector(".card__bookmark");
            bookmarkBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                const nowSaved = toggleSaveArticle(article);
                bookmarkBtn.innerHTML = nowSaved ? BOOKMARK_FILLED : BOOKMARK_OUTLINE;
                bookmarkBtn.classList.toggle("card__bookmark--saved", nowSaved);
            });

            swipeWrapper.appendChild(snapContainer);
            cardEls.push(snapContainer);
        });
    }

    // ── Feed / Saved View Toggling ──────────────────────────────────
    window.toggleSavedView = function () {
        const todayDateEl = document.getElementById("today-date");
        const btnBack = document.getElementById("btn-back");
        const headerTitle = document.getElementById("header-title");
        const headerActions = document.getElementById("header-actions");

        if (currentView === "feed") {
            feedIndex = currentIndex; // Save where we were in the feed
            currentView = "saved";

            // Update Header
            if (todayDateEl) todayDateEl.style.display = "none";
            if (btnBack) btnBack.style.display = "";
            if (headerTitle) headerTitle.textContent = "Saved Articles";
            if (headerActions) headerActions.style.display = "none";

            // Render saved articles
            const saved = getSavedArticles();
            if (saved.length === 0) {
                showEmpty("No saved articles yet. Tap the bookmark icon on any story.");
            } else {
                renderArticles(saved);
            }
        } else {
            currentView = "feed";

            // Update Header
            if (todayDateEl) todayDateEl.style.display = "";
            if (btnBack) btnBack.style.display = "none";
            if (headerTitle) headerTitle.textContent = "Daily AI News";
            if (headerActions) headerActions.style.display = "flex";

            // Render feed articles
            if (allArticles.length === 0) {
                showEmpty("No news for today.");
            } else {
                renderArticles(allArticles);
                // Restore previous position visually
                while (currentIndex < feedIndex && currentIndex < cardEls.length) {
                    const c = cardEls[currentIndex];
                    c.classList.add("snap-card--flipped");
                    c.style.transform = "";
                    c.style.filter = "";
                    currentIndex++;
                }
            }
        }
    };

    // ── Gesture Handling (mouse + touch + wheel/trackpad) ─────────────
    let wheelAccum = 0;             // accumulated horizontal wheel delta
    let wheelCooldown = false;      // prevents rapid-fire flips
    const WHEEL_THRESHOLD = 80;     // px of accumulated delta to trigger a flip
    const WHEEL_COOLDOWN_MS = 600;  // ms to wait between wheel-triggered flips

    function attachGestures() {
        // Prevent browser native drag (images, text selection drag)
        swipeWrapper.addEventListener("dragstart", (e) => e.preventDefault());

        // Mouse events (desktop drag)
        swipeWrapper.addEventListener("mousedown", onDown, false);
        document.addEventListener("mousemove", onMoveRaw, false);
        document.addEventListener("mouseup", onUp, false);

        // Touch events (mobile)
        swipeWrapper.addEventListener("touchstart", onTouchDown, { passive: true });
        document.addEventListener("touchmove", onTouchMoveRaw, { passive: false });
        document.addEventListener("touchend", onUp, { passive: true });
        document.addEventListener("touchcancel", onUp, { passive: true });

        // Wheel / trackpad two-finger swipe (macOS & others)
        swipeWrapper.addEventListener("wheel", onWheel, { passive: false });
    }

    function onWheel(e) {
        // Use deltaX for horizontal swipe; fall back to deltaY if deltaX is tiny
        // (some trackpads report mostly deltaY for horizontal two-finger swipes)
        const dx = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;

        if (dx === 0 || wheelCooldown) return;

        e.preventDefault(); // stop the page from scrolling

        wheelAccum += dx;

        if (wheelAccum > WHEEL_THRESHOLD) {
            // Swiped left → next article
            wheelAccum = 0;
            wheelCooldown = true;
            setTimeout(() => { wheelCooldown = false; }, WHEEL_COOLDOWN_MS);
            window.flipNext();
        } else if (wheelAccum < -WHEEL_THRESHOLD) {
            // Swiped right → previous article
            wheelAccum = 0;
            wheelCooldown = true;
            setTimeout(() => { wheelCooldown = false; }, WHEEL_COOLDOWN_MS);
            window.flipPrev();
        }
    }

    function onDown(e) {
        if (isAnimating || currentIndex >= cardEls.length) return;
        if (e.button !== undefined && e.button !== 0) return;

        // Don't initiate drag if clicking a link or button
        if (e.target.closest('a, button')) return;

        tracking = true;
        dragging = false;
        startX = e.clientX;
        flipProgress = 0;
    }

    function onTouchDown(e) {
        if (isAnimating || currentIndex >= cardEls.length) return;
        tracking = true;
        dragging = false;
        startX = e.touches[0].clientX;
        flipProgress = 0;
    }

    function processDrag(clientX) {
        if (!tracking || isAnimating || currentIndex >= cardEls.length) return;

        const deltaX = startX - clientX; // positive = swipe left

        // Dead zone — haven't started dragging yet
        if (!dragging) {
            if (Math.abs(deltaX) < DEAD_ZONE) return;
            dragging = true;
            const topCard = cardEls[currentIndex];
            topCard.classList.remove("snap-card--transitioning");
        }

        // Only flip on left-swipe
        if (deltaX <= 0) {
            applyFlip(0);
            return;
        }

        flipProgress = Math.min(deltaX / MAX_DRAG_PX, 1);
        applyFlip(flipProgress);
    }

    function onMoveRaw(e) {
        if (!tracking) return;
        if (dragging) e.preventDefault();
        processDrag(e.clientX);
    }

    function onTouchMoveRaw(e) {
        if (!tracking) return;
        const tx = e.touches[0].clientX;
        const deltaX = startX - tx;
        // Only prevent default scroll if we're actively doing a horizontal drag
        if (dragging && deltaX > 0) e.preventDefault();
        processDrag(tx);
    }

    function onUp() {
        if (!tracking) return;
        tracking = false;

        if (!dragging) return; // was a tap, let it through
        dragging = false;

        if (currentIndex >= cardEls.length) return;

        const topCard = cardEls[currentIndex];

        if (flipProgress >= FLIP_THRESHOLD) {
            // Unify swipe completion with smooth next button animation
            animateFlipForward(topCard, flipProgress);
        } else {
            topCard.classList.add("snap-card--transitioning");
            snapBack(topCard);
        }
    }

    // ── Public navigation (called by nav buttons) ───────────────────
    window.flipNext = function () {
        if (isAnimating || currentIndex >= cardEls.length) return;
        const topCard = cardEls[currentIndex];
        animateFlipForward(topCard);
    };

    window.flipPrev = function () {
        if (isAnimating || currentIndex <= 0) return;
        const prevIndex = currentIndex - 1;
        const prevCard = cardEls[prevIndex];
        animateFlipBack(prevCard);
    };

    /**
     * Smooth animated flip forward over ~1000ms using rAF.
     * Unifies Next button click (start=0) and swipe completion (start=flipProgress).
     */
    function animateFlipForward(cardEl, startProgress = 0) {
        isAnimating = true;
        const duration = 1000;
        const start = performance.now();

        function tick(now) {
            const elapsed = now - start;
            const t = Math.min(elapsed / duration, 1);
            // ease-out cubic
            const eased = 1 - Math.pow(1 - t, 3);

            // Interpolate from startProgress to fully flipped (1)
            const progress = startProgress + (1 - startProgress) * eased;

            const angle = progress * -180;
            const skew = Math.sin(progress * Math.PI) * 3;

            cardEl.style.transform = `rotateY(${angle}deg) skewY(${skew}deg)`;
            // Explicitly remove heavy drop-shadow to match "previous news" smoothness
            cardEl.style.filter = "none";

            if (t < 1) {
                requestAnimationFrame(tick);
            } else {
                // Flip complete
                cardEl.classList.add("snap-card--flipped");
                cardEl.style.transform = "";
                cardEl.style.filter = "";
                currentIndex++;
                flipProgress = 0;
                isAnimating = false;
            }
        }
        requestAnimationFrame(tick);
    }

    /**
     * Smooth animated flip backward over ~600ms using rAF.
     * Goes from -180° back to 0° with easing.
     */
    function animateFlipBack(cardEl) {
        isAnimating = true;
        const duration = 600;
        const start = performance.now();
        cardEl.classList.remove("snap-card--flipped");

        function tick(now) {
            const elapsed = now - start;
            const t = Math.min(elapsed / duration, 1);
            // ease-out cubic
            const eased = 1 - Math.pow(1 - t, 3);
            const progress = 1 - eased; // going from 1 back to 0
            const angle = progress * -180;
            const skew = Math.sin(progress * Math.PI) * 3;
            cardEl.style.transform = `rotateY(${angle}deg) skewY(${skew}deg)`;

            if (t < 1) {
                requestAnimationFrame(tick);
            } else {
                cardEl.style.transform = "";
                cardEl.style.filter = "";
                currentIndex--;
                flipProgress = 0;
                isAnimating = false;
            }
        }
        requestAnimationFrame(tick);
    }

    // ── Flip Rendering ──────────────────────────────────────────────
    function applyFlip(progress) {
        if (currentIndex >= cardEls.length) return;
        const topCard = cardEls[currentIndex];
        const angle = progress * -180;

        const skew = Math.sin(progress * Math.PI) * 3;
        topCard.style.transform =
            `rotateY(${angle}deg) skewY(${skew}deg)`;

        const shadowIntensity = Math.sin(progress * Math.PI) * 0.6;
        topCard.style.filter =
            `drop-shadow(${-8 * progress}px 0 ${16 * progress}px rgba(0,0,0,${shadowIntensity}))`;
    }

    function snapBack(cardEl) {
        cardEl.style.transform = "rotateY(0deg) skewY(0deg)";
        cardEl.style.filter = "none";

        cardEl.addEventListener("transitionend", function handler() {
            cardEl.removeEventListener("transitionend", handler);
            cardEl.classList.remove("snap-card--transitioning");
            cardEl.style.transform = "";
            cardEl.style.filter = "";
            flipProgress = 0;
        }, { once: true });
    }

    // ── Skeleton / Empty States ─────────────────────────────────────
    function showSkeletons(count) {
        swipeWrapper.innerHTML = "";
        for (let i = 0; i < count; i++) {
            const sk = document.createElement("div");
            sk.className = "empty-state";
            sk.innerHTML = `
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-surface-btn)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
            `;
            swipeWrapper.appendChild(sk);
        }
    }

    function showEmpty(msg) {
        swipeWrapper.innerHTML = `
            <div class="empty-state">
                <p>${msg}</p>
            </div>
        `;
    }

    // ── Settings View ────────────────────────────────────────────────
    let settingsViewOpen = false;
    const settingsContainer = document.getElementById("settings-container");

    window.toggleSettingsView = function () {
        if (!settingsContainer.hasAttribute("open")) {
            settingsContainer.showModal();
        } else {
            settingsContainer.close();
        }
    };

    window.installApp = function () {
        showToast("Install prompt would appear here");
    };

    window.showWhatsNew = function () {
        showToast("No new updates at this time");
    };

    window.refreshApp = function () {
        window.location.reload();
    };

    window.sendFeedback = function () {
        window.location.href = "mailto:feedback@pulse.app";
    };

    // Daily Reminder Push Notification API
    async function subscribeToPushNotifications() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) return false;
        try {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') return false;

            const swRegistration = await navigator.serviceWorker.ready;

            // Base64URL string extracted from pywebpush generator
            const publicVapidKey = 'BLr0ntXfzNiaKak8O1LPScZuDYG5m32GHu3mlsfgh2ltHBlMTNIx_d2Ul-Sj2yR-X9qObg894Lh4W_Sezc-jbZA';

            function urlB64ToUint8Array(base64String) {
                const padding = '='.repeat((4 - base64String.length % 4) % 4);
                const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
                const rawData = window.atob(base64);
                const outputArray = new Uint8Array(rawData.length);
                for (let i = 0; i < rawData.length; ++i) {
                    outputArray[i] = rawData.charCodeAt(i);
                }
                return outputArray;
            }

            const subscription = await swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlB64ToUint8Array(publicVapidKey)
            });

            const res = await fetch('/api/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(subscription)
            });
            return res.ok;
        } catch (e) {
            console.error("Push subscription mapping error", e);
            return false;
        }
    }

    const toggleReminder = document.getElementById("toggle-reminder");
    const reminderStatusText = document.getElementById("reminder-status-text");


    // Initialize state mapping natively from local storage
    if (localStorage.getItem("pulse-reminders") === "enabled") {
        if (toggleReminder) toggleReminder.checked = true;
        if (reminderStatusText) reminderStatusText.textContent = "On";
        if (footerAction) footerAction.style.display = "none";
    }

    const btnRemindOpts = document.querySelectorAll(".btn-remind, #toggle-reminder");
    btnRemindOpts.forEach(btn => {
        btn.addEventListener(btn.tagName === "INPUT" ? "change" : "click", async (e) => {
            const isTogglingOn = e.target.tagName === "INPUT" ? e.target.checked : true;

            if (isTogglingOn) {
                const success = await subscribeToPushNotifications();
                if (success) {
                    localStorage.setItem("pulse-reminders", "enabled");
                    if (toggleReminder) toggleReminder.checked = true;
                    if (reminderStatusText) reminderStatusText.textContent = "On";
                    if (footerAction) footerAction.style.display = "none"; /* Hide CTA */
                    showToast("Daily reminders enabled");
                } else {
                    if (toggleReminder) toggleReminder.checked = false;
                    showToast("Push permission denied by browser");
                }
            } else {
                localStorage.setItem("pulse-reminders", "disabled");
                if (reminderStatusText) reminderStatusText.textContent = "Off";
                showToast("Daily reminders disabled");
            }
        });
    });

    // ── Helpers ────────────────────────────────────────────────────
    function escapeHtml(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }
    // ── Offline Indicator ────────────────────────────────────────────
    const offlineBanner = document.getElementById("offline-banner");
    function updateOnlineStatus() {
        if (!navigator.onLine) {
            if (offlineBanner) offlineBanner.style.display = "block";
            showToast("Connection lost. Showing offline cache.");
        } else {
            if (offlineBanner) offlineBanner.style.display = "none";
        }
    }
    window.addEventListener("online", updateOnlineStatus);
    window.addEventListener("offline", updateOnlineStatus);
    updateOnlineStatus();

    // ── PWA Install Prompt ───────────────────────────────────────────
    let deferredPrompt;
    const installDrawer = document.getElementById("install-drawer");
    const btnInstallAccept = document.getElementById("btn-install-accept");
    const btnInstallDismiss = document.getElementById("btn-install-dismiss");

    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;

    if (!isStandalone) {
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            if (installDrawer) {
                installDrawer.classList.add('visible');
                installDrawer.style.display = "block";
            }
        });

        if (btnInstallAccept) {
            btnInstallAccept.addEventListener('click', async () => {
                if (installDrawer) installDrawer.classList.remove('visible');
                setTimeout(() => { if (installDrawer) installDrawer.style.display = "none"; }, 400);

                if (deferredPrompt) {
                    deferredPrompt.prompt();
                    const { outcome } = await deferredPrompt.userChoice;
                    console.log(`Techizo PWA Installation ${outcome}`);
                    deferredPrompt = null;
                }
            });
        }

        if (btnInstallDismiss) {
            btnInstallDismiss.addEventListener('click', () => {
                if (installDrawer) installDrawer.classList.remove('visible');
                setTimeout(() => { if (installDrawer) installDrawer.style.display = "none"; }, 400);
            });
        }
    }

    window.addEventListener('appinstalled', () => {
        if (installDrawer) installDrawer.classList.remove('visible');
        setTimeout(() => { if (installDrawer) installDrawer.style.display = "none"; }, 400);
        console.log('Techizo was installed heavily system-side.');
        showToast("Techizo installed successfully!");
    });

})();
