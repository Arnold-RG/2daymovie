/* 2DayMovie app shell: data loading, category rows, navbar and the embedded
   player modal. hero.js (carousel) and search.js plug in through window.TDM. */
(() => {
  "use strict";

  const ROW_LIMIT = 40;            // cards per row before "See all"
  const NOCOOKIE = "https://www.youtube-nocookie.com";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  const $ = (sel, root = document) => root.querySelector(sel);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const svg = (path) => {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("aria-hidden", "true");
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", path);
    s.appendChild(p);
    return s;
  };
  const ICON_PLAY = "M8 5v14l11-7z";
  const ICON_INFO = "M11 7h2v2h-2zm0 4h2v6h-2zm1-9a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16z";

  const thumb = (id, q = "mqdefault") => `https://i.ytimg.com/vi/${id}/${q}.jpg`;
  const fmtDuration = (s) => {
    const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
    if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
    return `${Math.max(1, m)} min`;
  };
  const fmtDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  const norm = (s) => s.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

  /* ---------------- YouTube consent (click-to-load) ----------------
     No request goes to youtube.com or youtube-nocookie.com until the visitor
     clicks or taps something that plays a video. That first click is stored
     as consent (localStorage "yt_consent" = "1"); later visits autoplay. */
  const CONSENT_KEY = "yt_consent";
  let consentMemo = null;
  function ytConsent() {
    if (consentMemo === null) {
      try { consentMemo = localStorage.getItem(CONSENT_KEY) === "1"; } catch (_) { consentMemo = false; }
    }
    return consentMemo;
  }
  function grantYTConsent() {
    if (ytConsent()) return;
    consentMemo = true;
    try { localStorage.setItem(CONSENT_KEY, "1"); } catch (_) { /* private mode: consent lasts for this page */ }
    document.dispatchEvent(new CustomEvent("tdm:yt-consent"));
  }

  /* ---------------- YouTube IFrame API ---------------- */
  let ytReady = null;
  function loadYT() {
    if (!ytConsent()) return Promise.reject(new Error("YouTube not loaded: no consent yet"));
    if (ytReady) return ytReady;
    ytReady = new Promise((resolve, reject) => {
      if (window.YT && window.YT.Player) return resolve(window.YT);
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { if (prev) prev(); resolve(window.YT); };
      const s = document.createElement("script");
      s.src = "https://www.youtube.com/iframe_api";
      s.async = true;
      s.onerror = () => reject(new Error("YouTube player could not load"));
      document.head.appendChild(s);
      setTimeout(() => reject(new Error("YouTube player timed out")), 15000);
    });
    return ytReady;
  }

  /* Every player iframe on the site is built here: youtube-nocookie.com only,
     sandboxed before its src is set, with the IFrame API enabled. */
  const SANDBOX = "allow-scripts allow-same-origin allow-presentation";
  function embedFrame(id, params = {}, title = "YouTube video player") {
    const f = document.createElement("iframe");
    f.setAttribute("sandbox", SANDBOX);
    const q = new URLSearchParams({ ...params, enablejsapi: "1", origin: location.origin });
    f.src = `${NOCOOKIE}/embed/${encodeURIComponent(id)}?${q}`;
    f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    f.allowFullscreen = true;
    f.title = title;
    f.referrerPolicy = "strict-origin-when-cross-origin";
    return f;
  }

  /* ---------------- data ---------------- */
  // Sections in page order; rows inside a section come from each item's first genre.
  const SECTIONS = [
    ["movies", "Movies"], ["series", "Series"], ["kids", "Kids"], ["cartoons", "Cartoons"],
    ["ai", "AI Animation / Manhwa"], ["wildlife", "Wildlife & Nature"],
  ];
  // catalog.json items: { id, title, type, genres[], duration, thumbnail }
  // trailers.json items: { title, release_date, youtube_id, start, end }
  let catalog = { sections: [], videos: [] };
  let trailers = [];
  const byId = new Map();

  async function loadData() {
    const base = document.documentElement.dataset.base || "";
    const [c, t] = await Promise.all([
      fetch(base + "data/catalog.json", { cache: "no-cache" }).then((r) => r.json()),
      fetch(base + "data/trailers.json", { cache: "no-cache" }).then((r) => r.json()),
    ]);
    const items = Array.isArray(c) ? c : c.items || [];
    catalog.generated = c.generated;
    catalog.videos = items.map((v) => ({ ...v, section: v.type, row: (v.genres && v.genres[0]) || "More to watch" }));
    catalog.sections = SECTIONS.filter(([id]) => catalog.videos.some((v) => v.section === id)).map(([id, title]) => ({
      id, title, rows: [...new Set(catalog.videos.filter((v) => v.section === id).map((v) => v.row))],
    }));
    trailers = (Array.isArray(t) ? t : t.items || []).map((x) => ({
      id: x.youtube_id, film: x.title, release: x.release_date, clip_start: x.start, clip_end: x.end,
    }));
    for (const v of catalog.videos) byId.set(v.id, v);
    for (const tr of trailers) byId.set(tr.id, { ...tr, title: tr.film, trailer: true });
  }

  /* ---------------- cards & rows ---------------- */
  function card(v, opts = {}) {
    const b = el("button", "card" + (opts.trailer ? " card--trailer" : ""));
    b.type = "button";
    b.dataset.id = v.id;
    b.appendChild(el("span", "sr", "Play "));  // the name comes from the visible text, prefixed with the action
    const th = el("div", "card__thumb");
    const img = el("img");
    img.loading = "lazy";
    img.decoding = "async";
    img.alt = "";
    // Right-sized thumbnails: 320px for most screens, 480px for wide or dense ones.
    img.srcset = `${thumb(v.id, "mqdefault")} 320w, ${thumb(v.id, "hqdefault")} 480w`;
    img.sizes = opts.trailer ? "(max-width: 520px) 78vw, (max-width: 1460px) 26vw, 380px" : "(max-width: 520px) 64vw, (max-width: 1430px) 21vw, 300px";
    img.src = thumb(v.id, "mqdefault");
    img.addEventListener("error", () => { img.style.visibility = "hidden"; }, { once: true });
    th.appendChild(img);
    const play = el("span", "card__play");
    play.appendChild(svg(ICON_PLAY));
    th.appendChild(play);
    if (opts.trailer) th.appendChild(el("span", "card__new", "Trailer"));
    th.appendChild(el("span", "card__badge", opts.trailer ? fmtDate(v.release) : fmtDuration(v.duration)));
    b.appendChild(th);
    b.appendChild(el("p", "card__title", opts.trailer ? v.film : v.title));
    const meta = opts.trailer ? "Official trailer" : [opts.rowLabel || v.row, v.year].filter(Boolean).join(" · ");
    b.appendChild(el("p", "card__meta", meta));
    return b;
  }

  function row(title, items, opts = {}) {
    const wrap = el("div", "row");
    const head = el("div", "row__head");
    head.appendChild(el("h3", "row__title", title));
    if (items.length > ROW_LIMIT) {
      const more = el("button", "row__more", `See all ${items.length}`);
      more.type = "button";
      more.addEventListener("click", () => showResults(title, items));
      head.appendChild(more);
    } else {
      head.appendChild(el("span", "row__count", `${items.length} titles`));
    }
    wrap.appendChild(head);
    const sc = el("div", "row__scroller");
    sc.setAttribute("role", "group");
    sc.setAttribute("aria-label", title);
    for (const v of items.slice(0, ROW_LIMIT)) sc.appendChild(card(v, opts));
    const prev = el("button", "row__btn row__btn--prev");
    prev.appendChild(svg("M15.4 5.4 14 4l-8 8 8 8 1.4-1.4L8.8 12z"));
    prev.setAttribute("aria-label", `Scroll ${title} left`);
    const next = el("button", "row__btn row__btn--next");
    next.appendChild(svg("M8.6 5.4 10 4l8 8-8 8-1.4-1.4 6.6-6.6z"));
    next.setAttribute("aria-label", `Scroll ${title} right`);
    const step = () => sc.clientWidth * 0.85;
    prev.addEventListener("click", () => sc.scrollBy({ left: -step(), behavior: reduceMotion.matches ? "auto" : "smooth" }));
    next.addEventListener("click", () => sc.scrollBy({ left: step(), behavior: reduceMotion.matches ? "auto" : "smooth" }));
    const sync = () => {
      prev.disabled = sc.scrollLeft < 8;
      next.disabled = sc.scrollLeft + sc.clientWidth >= sc.scrollWidth - 8;
    };
    sc.addEventListener("scroll", sync, { passive: true });
    requestAnimationFrame(sync);
    wrap.append(prev, sc, next);
    return wrap;
  }

  function renderBrowse() {
    const root = $("#browse");
    root.textContent = "";
    if (trailers.length) {
      const s = el("section", "section");
      s.id = "trailers";
      s.appendChild(el("h2", "section__title", "Upcoming Trailers"));
      s.appendChild(row("Coming soon to cinemas", trailers, { trailer: true }));
      root.appendChild(s);
    }
    for (const sec of catalog.sections) {
      const vids = catalog.videos.filter((v) => v.section === sec.id);
      if (!vids.length) continue;
      const s = el("section", "section");
      s.id = sec.id;
      s.appendChild(el("h2", "section__title", sec.title));
      for (const r of sec.rows) {
        const items = vids.filter((v) => v.row === r);
        if (items.length) s.appendChild(row(r, items, { rowLabel: r }));
      }
      root.appendChild(s);
    }
    renderGenres(root);
    $("#loading").hidden = true;
    const total = catalog.videos.length;
    $("#footerMeta").textContent = `${total} titles and ${trailers.length} upcoming trailers · catalog updated ${catalog.generated || ""}`;
  }

  /* ---------------- genre rows ---------------- */
  // genres[0] is the shelf row; genres[1:] are real genres. A genre row appears
  // only when it has at least GENRE_MIN titles.
  const GENRES = ["Drama", "Action", "Adventure", "Sci-Fi", "Musical", "Horror", "Comedy", "Romance", "Thriller", "Documentary"];
  const GENRE_MIN = 6;
  const genreSlug = (g) => "genre-" + g.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  let genreRows = [];

  function renderGenres(root) {
    genreRows = GENRES.map((g) => ({
      genre: g,
      items: catalog.videos.filter((v) => Array.isArray(v.genres) && v.genres.slice(1).includes(g)),
    })).filter((r) => r.items.length >= GENRE_MIN);
    const menu = $("#genreMenu");
    if (menu) menu.textContent = "";
    if (!genreRows.length) {
      const dd = $("#genreDropdown");
      if (dd) dd.hidden = true;
      return;
    }
    const s = el("section", "section");
    s.id = "genres";
    s.appendChild(el("h2", "section__title", "Genres"));
    for (const r of genreRows) {
      const rowEl = row(r.genre, r.items);
      rowEl.id = genreSlug(r.genre);
      s.appendChild(rowEl);
      if (menu) {
        const li = el("li");
        const a = el("a", "", `${r.genre}`);
        a.href = `#${genreSlug(r.genre)}`;
        a.dataset.nav = "genres";
        li.appendChild(a);
        menu.appendChild(li);
      }
    }
    root.appendChild(s);
  }

  /* ---------------- search / see all ---------------- */
  let lastScroll = 0;
  function showResults(title, items) {
    if (!document.body.classList.contains("is-results")) lastScroll = window.scrollY;
    document.body.classList.add("is-results");
    $("#results").hidden = false;
    $("#resultsTitle").textContent = title;
    const grid = $("#resultsGrid");
    grid.textContent = "";
    const frag = document.createDocumentFragment();
    for (const v of items) frag.appendChild(card(v, { trailer: !!v.trailer || !!v.film }));
    grid.appendChild(frag);
    $("#resultsEmpty").hidden = items.length > 0;
    window.scrollTo(0, 0);
    hero.pause("results");
  }
  function hideResults() {
    if (!document.body.classList.contains("is-results")) return;
    document.body.classList.remove("is-results");
    $("#results").hidden = true;
    window.scrollTo(0, lastScroll);
    hero.resume("results");
  }
  /* ---------------- modal player ---------------- */
  let modalPlayer = null;
  let lastFocus = null;
  // userAction: a click or tap on a card / button. That counts as consent to load YouTube.
  function openPlayer(id, userAction = true) {
    const v = byId.get(id);
    if (!v) return;
    if (userAction) grantYTConsent();
    const modal = $("#player");
    if (modal.hidden) lastFocus = document.activeElement;
    modal.hidden = false;
    document.body.classList.add("modal-open");
    $("#playerTitle").textContent = v.trailer ? `${v.film}: official trailer` : v.title;
    $("#playerMeta").textContent = v.trailer
      ? `In cinemas ${fmtDate(v.release)}`
      : [v.row, v.year, fmtDuration(v.duration)].filter(Boolean).join(" · ");
    $("#playerError").hidden = true;
    hero.pause("modal");
    const url = new URL(location.href);
    url.searchParams.set("v", id);
    history.replaceState(null, "", url);
    const host = $("#playerFrame");
    host.textContent = "";
    if (!ytConsent()) {
      // Opened from a shared ?v= link: ask before contacting YouTube.
      const gate = el("div", "modal__gate");
      const img = el("img", "modal__gate-img");
      img.alt = "";
      img.src = thumb(id, "hqdefault");
      const btn = el("button", "btn btn--play modal__gate-btn");
      btn.type = "button";
      btn.append(svg(ICON_PLAY), document.createTextNode("Play video"));
      btn.addEventListener("click", () => openPlayer(id, true));
      const note = el("p", "consent-note", "Video by YouTube, loads YouTube cookies");
      gate.append(img, btn, note);
      host.appendChild(gate);
      btn.focus();
      return;
    }
    // Our own sandboxed iframe; the IFrame API then attaches to it for error events.
    const frame = embedFrame(id, { autoplay: 1, rel: 0, playsinline: 1, modestbranding: 1, iv_load_policy: 3 }, v.title);
    host.textContent = "";
    host.appendChild(frame);
    loadYT().then((YT) => {
      if (modal.hidden || !frame.isConnected) return;
      modalPlayer = new YT.Player(frame, {
        events: { onError: () => { $("#playerError").hidden = false; } },
      });
    }).catch(() => { /* the plain sandboxed embed keeps playing without the API */ });
    $(".modal__close").focus();
  }
  function closePlayer() {
    const modal = $("#player");
    if (modal.hidden) return;
    if (modalPlayer && modalPlayer.destroy) modalPlayer.destroy();
    modalPlayer = null;
    $("#playerFrame").textContent = "";
    modal.hidden = true;
    document.body.classList.remove("modal-open");
    const url = new URL(location.href);
    url.searchParams.delete("v");
    history.replaceState(null, "", url);
    hero.resume("modal");
    if (lastFocus) lastFocus.focus();
  }

  // Hero carousel lives in hero.js; it registers TDM.hero. Calls are no-ops until then.
  const hero = {
    pause: (r) => TDM.hero && TDM.hero.pause(r),
    resume: (r) => TDM.hero && TDM.hero.resume(r),
  };

  /* ---------------- nav ---------------- */
  function bindNav() {
    const nav = $("#nav");
    const onScroll = () => nav.classList.toggle("is-solid", window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    const toggle = $("#navToggle"), links = $("#navLinks");
    toggle.addEventListener("click", () => {
      const open = links.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    const ddBtn = $("#genreToggle"), ddMenu = $("#genreMenu");
    const setDD = (open) => {
      if (!ddBtn) return;
      ddBtn.setAttribute("aria-expanded", String(open));
      ddMenu.hidden = !open;
    };
    if (ddBtn) {
      ddBtn.addEventListener("click", (e) => { e.stopPropagation(); setDD(ddMenu.hidden); });
      document.addEventListener("click", (e) => { if (!e.target.closest("#genreDropdown")) setDD(false); });
      document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !ddMenu.hidden) { setDD(false); ddBtn.focus(); } });
    }
    links.addEventListener("click", (e) => {
      if (!e.target.closest("a")) return;
      setDD(false);
      links.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
      hideResults();
      $("#searchInput").value = "";
    });
    const anchors = [...links.querySelectorAll("a"), ...(ddBtn ? [ddBtn] : [])];
    const io = new IntersectionObserver((entries) => {
      for (const en of entries) {
        if (!en.isIntersecting) continue;
        const id = en.target.id;
        anchors.forEach((a) => a.classList.toggle("is-active", a.dataset.nav === id));
      }
    }, { rootMargin: "-45% 0px -50% 0px" });
    ["top", "trailers", ...catalog.sections.map((s) => s.id), "genres"].forEach((id) => {
      const n = document.getElementById(id);
      if (n) io.observe(n);
    });
  }

  function bindGlobal() {
    document.addEventListener("click", (e) => {
      const c = e.target.closest(".card");
      if (c) { openPlayer(c.dataset.id); return; }
      if (e.target.closest("[data-close]")) closePlayer();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (!$("#player").hidden) closePlayer();
        else if (document.body.classList.contains("is-results")) { $("#searchInput").value = ""; hideResults(); }
      }
    });
    const input = $("#searchInput");
    $("#resultsClose").addEventListener("click", () => { input.value = ""; hideResults(); });
  }

  async function init() {
    try {
      await loadData();
    } catch (err) {
      $("#loading").textContent = "The catalog could not be loaded. Please refresh the page.";
      return;
    }
    renderBrowse();
    bindGlobal();
    bindNav();
    document.dispatchEvent(new CustomEvent("tdm:ready"));
    // Landing pages (/explore/<slug>/) open at their section or genre row.
    const start = document.documentElement.dataset.start;
    const target = start && document.getElementById(start);
    if (target) requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
    const v = new URL(location.href).searchParams.get("v");
    if (v && byId.has(v)) openPlayer(v, false);
  }

  // Shared API for hero.js and search.js
  const TDM = (window.TDM = window.TDM || {});
  Object.assign(TDM, {
    $, el, svg, thumb, fmtDate, fmtDuration, norm, loadYT, openPlayer, embedFrame, SANDBOX, showResults, hideResults,
    ICON_PLAY, ICON_INFO, NOCOOKIE, reduceMotion, ytConsent, grantYTConsent,
  });
  Object.defineProperties(TDM, {
    catalog: { get: () => catalog, configurable: true },
    trailers: { get: () => trailers, configurable: true },
  });

  init();
})();
