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

    function resolveThemeToLightOrDark(theme) {
        if (theme === "light") return "light";
        if (theme === "dark") return "dark";
        return prefersDarkQuery.matches ? "dark" : "light"; // system
    }

    function applyTheme(theme) {
        const el = document.documentElement;
        el.classList.remove("dark", "light", "her");

        const prefersDark = prefersDarkQuery.matches;
        if (!theme) theme = "system";

        if (theme === "system") {
            el.classList.add(prefersDark ? "dark" : "light");
            setMetaColor(prefersDark ? "#171717" : "#ffffff");
        } else if (theme === "light") {
            el.classList.add("light");
            setMetaColor("#ffffff");
        } else {
            el.classList.add("dark");
            setMetaColor("#171717");
        }

        updateStarsTheme();
        updateStarsVisibility();
    }

    function updateThemeButton(theme) {
        const btn = document.getElementById("owui-theme-btn");
        if (!btn) return;

        const sun = `
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z" stroke="currentColor" stroke-width="2"/>
        <path d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M5 19l1.5-1.5"
          stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>`;
        const moon = `
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M21 13.2A8.2 8.2 0 1 1 10.8 3 6.5 6.5 0 0 0 21 13.2Z"
          stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
      </svg>`;
        const monitor = `
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M4 5h16v11H4z" stroke="currentColor" stroke-width="2" />
        <path d="M8 21h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <path d="M12 16v5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>`;

        if (theme === "light") btn.innerHTML = sun;
        else if (theme === "dark") btn.innerHTML = moon;
        else btn.innerHTML = monitor;
    }

    function playThemeOverlay(nextResolved) {
        const overlay = document.createElement("div");
        Object.assign(overlay.style, {
            position: "fixed",
            inset: "0",
            pointerEvents: "none",
            zIndex: String(Z_THEME_OVERLAY),
            opacity: "0",
            background: nextResolved === "light" ? "#ffffff" : "#000000",
        });
        document.documentElement.appendChild(overlay);

        const anim = overlay.animate(
            [{ opacity: 0 }, { opacity: THEME_ANIM_PEAK_OPACITY }, { opacity: 0 }],
            { duration: THEME_ANIM_DURATION_MS, easing: "ease-in-out" }
        );
        anim.onfinish = () => overlay.remove();
    }

    function setTheme(theme) {
        localStorage.theme = theme;

        const resolved = resolveThemeToLightOrDark(theme);
        playThemeOverlay(resolved);

        window.setTimeout(() => {
            applyTheme(theme);
            updateThemeButton(theme);
        }, Math.floor(THEME_ANIM_DURATION_MS * 0.35));
    }

    // system changes
    const systemChangeHandler = () => {
        if (getTheme() === "system") applyTheme("system");
    };
    if (prefersDarkQuery.addEventListener) prefersDarkQuery.addEventListener("change", systemChangeHandler);
    else if (prefersDarkQuery.addListener) prefersDarkQuery.addListener(systemChangeHandler);

    // ---------------------------
    // STARS BACKGROUND (LOGIN ONLY, ANIMATED)
    // ---------------------------
    let starsWrap = null;
    let starsCanvas = null;
    let starsCtx = null;
    let stars = [];
    let starsRunning = false;
    let starsRaf = 0;
    let lastT = 0;

    function isLoginScreen() {
        // If chat input exists, it's NOT login
        const chatInput =
            document.querySelector("textarea") ||
            document.querySelector('[contenteditable="true"]');
        if (chatInput) return false;

        // Detect password field even when toggled to text ("show password")
        const inputs = Array.from(document.querySelectorAll("input"));

        const looksLikePassword = (el) => {
            const t = (el.getAttribute("type") || "").toLowerCase();
            const name = (el.getAttribute("name") || "").toLowerCase();
            const id = (el.getAttribute("id") || "").toLowerCase();
            const ph = (el.getAttribute("placeholder") || "").toLowerCase();
            const al = (el.getAttribute("aria-label") || "").toLowerCase();
            const ac = (el.getAttribute("autocomplete") || "").toLowerCase();

            return (
                t === "password" ||
                ac.includes("password") ||
                name.includes("password") ||
                id.includes("password") ||
                ph.includes("password") ||
                ph.includes("passwort") ||
                al.includes("password") ||
                al.includes("passwort")
            );
        };

        return inputs.some(looksLikePassword);
    }

    function updateStarsTheme() {
        if (!starsWrap) return;
        const resolved = resolveThemeToLightOrDark(getTheme());
        starsWrap.style.background =
            resolved === "dark"
                ? "radial-gradient(ellipse at bottom, #262626 0%, #000 100%)"
                : "radial-gradient(ellipse at bottom, #f5f5f5 0%, #fff 100%)";
    }

    function getStarRGB() {
        const resolved = resolveThemeToLightOrDark(getTheme());
        return resolved === "dark" ? [255, 255, 255] : [0, 0, 0];
    }

    function ensureStars() {
        if (starsWrap) return;

        starsWrap = document.createElement("div");
        starsWrap.id = "owui-stars-wrap";
        Object.assign(starsWrap.style, {
            position: "fixed",
            inset: "0",
            zIndex: String(Z_STARS),
            pointerEvents: "none",
            overflow: "hidden",
            display: "none",
        });

        starsCanvas = document.createElement("canvas");
        starsCanvas.id = "owui-stars";
        Object.assign(starsCanvas.style, { width: "100%", height: "100%", display: "block" });

        starsWrap.appendChild(starsCanvas);
        document.documentElement.appendChild(starsWrap);

        starsCtx = starsCanvas.getContext("2d", { alpha: true });

        resizeStars();
        initStars();
        updateStarsTheme();
    }

    function resizeStars() {
        if (!starsCanvas) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        starsCanvas._dpr = dpr;
        starsCanvas.width = Math.floor(window.innerWidth * dpr);
        starsCanvas.height = Math.floor(window.innerHeight * dpr);
    }

    function initStars() {
        if (!starsCanvas) return;
        const dpr = starsCanvas._dpr || 1;
        const w = starsCanvas.width;
        const h = starsCanvas.height;

        const count = Math.max(90, Math.min(320, Math.floor((w * h) / (dpr * dpr * STARS_DENSITY))));

        stars = new Array(count).fill(0).map(() => {
            const z = Math.random() * 0.9 + 0.1; // depth factor
            return {
                x: Math.random() * w,
                y: Math.random() * h,
                r: (Math.random() * 1.1 + 0.4) * dpr * (0.5 + z),
                v: ((Math.random() * (STARS_SPEED_MAX - STARS_SPEED_MIN) + STARS_SPEED_MIN) * dpr) * (0.3 + z),
                ph: Math.random() * Math.PI * 2,
                tw: Math.random() * 1.2 + 0.6,
                a0: Math.random() * 0.35 + 0.25,
                aa: Math.random() * 0.45 + 0.25,
            };
        });
    }

    function startStars() {
        if (starsRunning) return;
        starsRunning = true;
        lastT = performance.now();
        starsRaf = requestAnimationFrame(tickStars);
    }

    function stopStars() {
        starsRunning = false;
        if (starsRaf) cancelAnimationFrame(starsRaf);
        starsRaf = 0;
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

        const ctx = starsCtx;
        const w = starsCanvas.width;
        const h = starsCanvas.height;

        ctx.clearRect(0, 0, w, h);

        const [sr, sg, sb] = getStarRGB();
        const time = t / 1000;

        for (let i = 0; i < stars.length; i++) {
            const s = stars[i];

            s.y += s.v * dt;
            if (s.y > h + 10) {
                s.y = -10;
                s.x = Math.random() * w;
            }

            const a = s.a0 + s.aa * (0.5 + 0.5 * Math.sin(time * s.tw + s.ph));

            ctx.beginPath();
            ctx.fillStyle = `rgba(${sr},${sg},${sb},${a})`;
            ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
            ctx.fill();
        }

        starsRaf = requestAnimationFrame(tickStars);
    }

    function setupStarsObservers() {
        const mo = new MutationObserver(() => updateStarsVisibility());
        mo.observe(document.body, { childList: true, subtree: true });

        window.addEventListener("popstate", updateStarsVisibility);

        const _pushState = history.pushState;
        history.pushState = function () {
            _pushState.apply(this, arguments);
            updateStarsVisibility();
        };
        const _replaceState = history.replaceState;
        history.replaceState = function () {
            _replaceState.apply(this, arguments);
            updateStarsVisibility();
        };
    }

    // ---------------------------
    // DOMContentLoaded: inject all
    // ---------------------------
    document.addEventListener("DOMContentLoaded", () => {
        const root = document.createElement("div");
        root.id = "owui-custom-root";
        document.documentElement.appendChild(root);

        const style = document.createElement("style");
        style.textContent = `
      html, body, * { cursor: none !important; }

      #owui-theme-ui {
        position: fixed;
        right: 16px;
        bottom: 16px;
        z-index: ${Z_THEME_UI};
        pointer-events: auto;
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
      #owui-theme-btn svg { width: 20px; height: 20px; }
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
        document.documentElement.appendChild(ui);

        // Init theme + button
        if (!localStorage.theme) localStorage.theme = "system";
        applyTheme(getTheme());
        updateThemeButton(getTheme());
    });
})();
