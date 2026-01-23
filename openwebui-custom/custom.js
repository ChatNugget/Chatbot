(() => {
    if (!window.matchMedia || !window.matchMedia("(pointer: fine)").matches) return;

    // ---------------------------
    // SETTINGS
    // ---------------------------
    const CURSOR_SIZE = 24;
    const HOTSPOT_X = 2;
    const HOTSPOT_Y = 3;

    const THEME_MODES = ["light", "dark", "system"];

    // Layering
    const Z_STARS = 0;                 // login-only background
    const Z_THEME_UI = 2147483645;     // theme button
    const Z_THEME_OVERLAY = 2147483646;
    const Z_CURSOR_LAYER = 2147483647; // cursor always on top

    // Theme click overlay animation (lightweight)
    const THEME_ANIM_DURATION_MS = 220;
    const THEME_ANIM_PEAK_OPACITY = 0.16;

    // Stars config
    const STARS_DENSITY = 16000;       // smaller = more stars
    const STARS_SPEED_MIN = 6;         // px/s
    const STARS_SPEED_MAX = 18;        // px/s

    // Guard
    if (document.getElementById("owui-custom-root")) return;

    // ---------------------------
    // THEME helpers
    // ---------------------------
    const prefersDarkQuery = window.matchMedia("(prefers-color-scheme: dark)");

    function metaThemeColorTag() {
        return document.querySelector('meta[name="theme-color"]');
    }

    function setMetaColor(hex) {
        const tag = metaThemeColorTag();
        if (tag) tag.setAttribute("content", hex);
    }

    function getTheme() {
        return localStorage.theme || "system";
    }

    function resolveTheme(theme) {
        if (theme === "dark" || theme === "light") return theme;
        return prefersDarkQuery.matches ? "dark" : "light";
    }

    function applyTheme(theme) {
        const el = document.documentElement;
        const resolved = resolveTheme(theme);

        el.classList.remove("dark", "light");
        el.classList.add(resolved);

        setMetaColor(resolved === "dark" ? "#0b0b0c" : "#ffffff");

        updateStarsTheme();
        updateStarsVisibility();
    }

    function animateThemeChange(theme) {
        const resolved = resolveTheme(theme);
        const overlay = document.createElement("div");
        Object.assign(overlay.style, {
            position: "fixed",
            inset: "0",
            background: resolved === "dark" ? "#0b0b0c" : "#ffffff",
            opacity: "0",
            pointerEvents: "none",
            zIndex: String(Z_THEME_OVERLAY),
            transition: `opacity ${THEME_ANIM_DURATION_MS}ms ease`,
        });

        document.body.appendChild(overlay);

        requestAnimationFrame(() => {
            overlay.style.opacity = String(THEME_ANIM_PEAK_OPACITY);
        });

        setTimeout(() => {
            overlay.style.opacity = "0";
        }, Math.floor(THEME_ANIM_DURATION_MS * 0.55));

        setTimeout(() => overlay.remove(), THEME_ANIM_DURATION_MS + 60);
    }

    function setTheme(theme) {
        localStorage.theme = theme;
        applyTheme(theme);
        updateThemeButton(theme);
        animateThemeChange(theme);
    }

    function updateThemeButton(theme) {
        const btn = document.getElementById("owui-theme-btn");
        if (!btn) return;

        // Monitor (System)
        const svgSystem = `
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 5.5C4 4.67 4.67 4 5.5 4h13C19.33 4 20 4.67 20 5.5v9.5c0 .83-.67 1.5-1.5 1.5h-13C4.67 16.5 4 15.83 4 15V5.5Z"
            stroke="currentColor" stroke-width="2" />
      <path d="M9 20h6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      <path d="M12 16.5V20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>`;

        // Sonne
        const svgSun = `
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z" stroke="currentColor" stroke-width="2"/>
      <path d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M5 19l1.5-1.5"
            stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>`;

        // Mond (zentrierter)
        const svgMoon = `
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M21 14.5A8.5 8.5 0 0 1 9.5 3a7 7 0 1 0 11.5 11.5Z"
            stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
    </svg>`;

        const resolved = resolveTheme(theme);
        btn.innerHTML = theme === "system" ? svgSystem : (resolved === "dark" ? svgMoon : svgSun);
    }


    // ---------------------------
    // Stars (login only)
    // ---------------------------
    let starsWrap = null;
    let starsCanvas = null;
    let starsCtx = null;
    let stars = [];
    let starsRunning = false;
    let lastT = 0;
    let rafStars = 0;

    function isLoginScreen() {
        const p = (location.pathname || "").toLowerCase();
        if (p.includes("signin") || p.includes("sign-in") || p.includes("login") || p.includes("auth")) return true;
        const pw = document.querySelector('input[type="password"]');
        return !!(pw && pw.offsetParent !== null);
    }

    function ensureStars() {
        if (starsWrap) return;

        starsWrap = document.createElement("div");
        Object.assign(starsWrap.style, {
            position: "fixed",
            inset: "0",
            zIndex: String(Z_STARS),
            pointerEvents: "none",
        });

        starsCanvas = document.createElement("canvas");
        Object.assign(starsCanvas.style, {
            width: "100%",
            height: "100%",
            display: "block",
        });

        starsWrap.appendChild(starsCanvas);
        document.body.appendChild(starsWrap);

        starsCtx = starsCanvas.getContext("2d", { alpha: true });
        resizeStars();
        initStars();
    }

    function resizeStars() {
        if (!starsCanvas || !starsCtx) return;
        const dpr = Math.max(1, window.devicePixelRatio || 1);
        starsCanvas.width = Math.floor(window.innerWidth * dpr);
        starsCanvas.height = Math.floor(window.innerHeight * dpr);
        starsCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function initStars() {
        const w = window.innerWidth;
        const h = window.innerHeight;
        const count = Math.max(60, Math.floor((w * h) / STARS_DENSITY));
        stars = Array.from({ length: count }, () => ({
            x: Math.random() * w,
            y: Math.random() * h,
            r: 0.6 + Math.random() * 1.6,
            v: STARS_SPEED_MIN + Math.random() * (STARS_SPEED_MAX - STARS_SPEED_MIN),
            a: 0.25 + Math.random() * 0.75,
        }));
    }

    function starsColor() {
        const theme = resolveTheme(getTheme());
        return theme === "dark" ? "255,255,255" : "0,0,0";
    }

    function startStars() {
        if (starsRunning) return;
        starsRunning = true;
        lastT = performance.now();
        rafStars = requestAnimationFrame(tickStars);
    }

    function stopStars() {
        starsRunning = false;
        if (rafStars) cancelAnimationFrame(rafStars);
        rafStars = 0;
        if (starsCtx && starsCanvas) starsCtx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    }

    function updateStarsTheme() {
        // no-op; draw uses starsColor() each frame
    }

    function updateStarsVisibility() {
        if (!starsWrap) return;
        const show = isLoginScreen();
        starsWrap.style.display = show ? "block" : "none";
        if (show) startStars();
        else stopStars();
    }

    function tickStars(t) {
        if (!starsRunning || !starsCanvas || !starsCtx) return;

        const dt = Math.min(0.05, (t - lastT) / 1000);
        lastT = t;

        const w = window.innerWidth;
        const h = window.innerHeight;

        starsCtx.clearRect(0, 0, w, h);

        const rgb = starsColor();
        for (const s of stars) {
            s.y += s.v * dt;
            if (s.y > h + 2) {
                s.y = -2;
                s.x = Math.random() * w;
            }
            starsCtx.globalAlpha = s.a;
            starsCtx.fillStyle = `rgb(${rgb})`;
            starsCtx.beginPath();
            starsCtx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
            starsCtx.fill();
        }
        starsCtx.globalAlpha = 1;

        rafStars = requestAnimationFrame(tickStars);
    }

    function setupStarsObservers() {
        const mo = new MutationObserver(() => updateStarsVisibility());
        mo.observe(document.body, { childList: true, subtree: true });

        window.addEventListener("resize", () => {
            resizeStars();
            initStars();
            updateStarsVisibility();
        }, { passive: true });
    }

    // ---------------------------
    // DOMContentLoaded: inject all
    // ---------------------------
    document.addEventListener("DOMContentLoaded", () => {
        const root =
            document.createElement("div");
        root.id = "owui-custom-root";
        document.documentElement.appendChild(root);

        const style = document.createElement("style");
        style.textContent = `
      html, body, * { cursor: none !important; }

      #owui-theme-ui {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        z-index: ${Z_THEME_UI};
        pointer-events: auto;
        flex: 0 0 auto;
      }

      /* Fallback (z.B. Login): floating unten rechts */
      #owui-theme-ui.owui-floating {
        position: fixed;
        right: 16px;
        bottom: 16px;
      }

      /* Composer-Row: Eingabe schrumpft, Theme bleibt rechts daneben */
      #owui-composer-row {
        display: flex;
        align-items: center;
        gap: 12px;
        width: 100%;
        max-width: 100%;
        flex-wrap: nowrap;
      }

      #owui-composer-row > #message-input-container {
        flex: 1 1 auto;
        min-width: 0 !important;
        width: auto !important;
      }

      /* zusätzliche Shrink-Sicherheit */
      #message-input-container,
      #chat-input-container,
      #chat-input {
        min-width: 0 !important;
      }

      #owui-theme-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.18);
        background: rgba(20,20,20,0.55);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        box-shadow: 0 6px 18px rgba(0,0,0,0.25);
        color: rgba(255,255,255,0.92);
        transition: filter 120ms ease;
      }

      html.light #owui-theme-btn {
        border: 1px solid rgba(0,0,0,0.12);
        background: rgba(255,255,255,0.70);
        color: rgba(0,0,0,0.85);
      }

      #owui-theme-btn:hover { filter: brightness(1.06); }
      #owui-theme-btn svg {
          width: 20px;
          height: 20px;
          display: block;
        }
        #owui-theme-btn {
          line-height: 0; /* verhindert vertikales "wackeln" */
        }

    `;
        document.head.appendChild(style);

        // Stars (login only)
        ensureStars();
        setupStarsObservers();
        window.addEventListener("resize", () => {
            resizeStars();
            initStars();
        });
        updateStarsTheme();
        updateStarsVisibility();

        // Cursor layer (always on top)
        const layer = document.createElement("div");
        layer.id = "owui-cursor-layer";
        Object.assign(layer.style, {
            position: "fixed",
            inset: "0",
            pointerEvents: "none",
            zIndex: String(Z_CURSOR_LAYER),
            overflow: "visible",
            isolation: "isolate",
        });

        const cursor = document.createElement("div");
        Object.assign(cursor.style, {
            position: "absolute",
            left: "0px",
            top: "0px",
            width: `${CURSOR_SIZE}px`,
            height: `${CURSOR_SIZE}px`,
            pointerEvents: "none",
            opacity: "0",
            transition: "opacity 120ms ease",
            willChange: "transform",
            mixBlendMode: "normal",
            filter:
                "drop-shadow(0 0 1px rgba(0,0,0,0.9)) drop-shadow(0 0 6px rgba(0,0,0,0.35))",
        });

        cursor.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="${CURSOR_SIZE}" height="${CURSOR_SIZE}">
        <path fill="white"
          d="M1.8 4.4 7 36.2c.3 1.8 2.6 2.3 3.6.8l3.9-5.7c1.7-2.5 4.5-4.1 7.5-4.3l6.9-.5c1.8-.1 2.5-2.4 1.1-3.5L5 2.5c-1.4-1.1-3.5 0-3.3 1.9Z"
        />
      </svg>
    `;

        layer.appendChild(cursor);
        document.documentElement.appendChild(layer);

        // Cursor motion
        let tx = 0, ty = 0;
        let x = 0, y = 0;
        let visible = false;

        window.addEventListener("mousemove", (e) => {
            tx = e.clientX;
            ty = e.clientY;
            if (!visible) {
                visible = true;
                cursor.style.opacity = "1";
            }
        });

        window.addEventListener("mouseleave", () => {
            visible = false;
            cursor.style.opacity = "0";
        });

        function tickCursor() {
            x += (tx - x) * 0.45;
            y += (ty - y) * 0.45;
            cursor.style.transform = `translate3d(${x - HOTSPOT_X}px, ${y - HOTSPOT_Y}px, 0)`;
            requestAnimationFrame(tickCursor);
        }
        requestAnimationFrame(tickCursor);

        // Theme toggle
        const ui = document.createElement("div");
        ui.id = "owui-theme-ui";

        const btn = document.createElement("button");
        btn.id = "owui-theme-btn";
        btn.type = "button";
        btn.title = "Toggle theme";
        btn.setAttribute("aria-label", "Toggle theme");

        btn.addEventListener("click", () => {
            const current = getTheme();
            const idx = THEME_MODES.indexOf(current);
            const next =
                THEME_MODES[(idx + 1 + THEME_MODES.length) % THEME_MODES.length] ||
                THEME_MODES[0];
            setTheme(next);
        });

        ui.appendChild(btn);
        ui.classList.add("owui-floating");
        document.body.appendChild(ui);

        // Theme-Button: separat rechts neben der gesamten Eingabe-Box (nicht im Send-Cluster)
        function dockThemeButton() {
            const mic = document.getElementById("message-input-container");
            if (!mic || !mic.parentElement) {
                // Fallback floating
                ui.classList.add("owui-floating");
                if (ui.parentElement !== document.body) document.body.appendChild(ui);
                return;
            }

            // Wrapper nur einmal anlegen, genau dort wo message-input-container sitzt
            let row = document.getElementById("owui-composer-row");
            if (!row || !row.contains(mic)) {
                row = document.createElement("div");
                row.id = "owui-composer-row";

                // message-input-container an die Stelle des Wrappers setzen
                mic.parentElement.insertBefore(row, mic);
                row.appendChild(mic);
            }

            // Theme UI als rechter "Side"-Button neben der Box
            if (ui.parentElement !== row) row.appendChild(ui);
            ui.classList.remove("owui-floating");

            // optisch: mittig zur Box
            ui.style.alignSelf = "center";
        }

        // SPA / Re-renders: regelmäßig nachdocken
        let dockRaf = 0;
        const scheduleDock = () => {
            if (dockRaf) return;
            dockRaf = requestAnimationFrame(() => {
                dockRaf = 0;
                dockThemeButton();
            });
        };

        scheduleDock();
        setTimeout(scheduleDock, 250);
        setTimeout(scheduleDock, 900);

        const dockObserver = new MutationObserver(scheduleDock);
        dockObserver.observe(document.body, { childList: true, subtree: true });

        window.addEventListener("resize", scheduleDock, { passive: true });

        // Init theme + button
        if (!localStorage.theme) localStorage.theme = "system";
        applyTheme(getTheme());
        updateThemeButton(getTheme());
    });
})();
