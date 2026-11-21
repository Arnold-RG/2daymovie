/* 2DayMovie phone navigation: the floating glass tab bar (phones, small tablets and
   phones in landscape) and its sheets: Search, Browse (sections and genres) and My List.
   Plugs into app.js through window.TDM, like hero.js and search.js. */
(() => {
  "use strict";
  const TDM = (window.TDM = window.TDM || {});
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  const phone = window.matchMedia("(max-width: 900px), (max-width: 1000px) and (max-height: 500px)");
  const LONG_PRESS_MS = 480;
  let $, el, tile, myList;

  /* Outline of the bar: a rounded pill whose top edge rises into a smooth bump at the centre.
     w, h: element size; bump: how far the bump rises above the bar; r: corner radius. */
  function barShape(w, h, bump, r) {
    const top = bump, bot = h, cx = w / 2;
    const hw = Math.min(58, w * 0.16);   // half width of the bump's base
    const edge = `M ${r} ${top} L ${cx - hw} ${top} C ${cx - hw * 0.55} ${top} ${cx - hw * 0.62} 0 ${cx} 0 C ${cx + hw * 0.62} 0 ${cx + hw * 0.55} ${top} ${cx + hw} ${top} L ${w - r} ${top}`;
    const outline = `${edge} A ${r} ${r} 0 0 1 ${w} ${top + r} L ${w} ${bot - r} A ${r} ${r} 0 0 1 ${w - r} ${bot} L ${r} ${bot} A ${r} ${r} 0 0 1 0 ${bot - r} L 0 ${top + r} A ${r} ${r} 0 0 1 ${r} ${top} Z`;
    return { edge, outline };
  }

  function init() {
    ({ $, el, tile, myList } = TDM);
    const bar = $("#tabbar");
    if (!bar) return;
    const inner = $("#tabInner"), glass = $("#tabGlass"), dot = $("#tabDot");
    const tabs = [...bar.querySelectorAll(".tab[data-tab]")];
    const tabOf = (name) => tabs.find((t) => t.dataset.tab === name);
    const badge = $("#listBadge");
    let active = "home", openSheet = null, lastFocus = null;

    /* ---------- shape: clip the glass to the bump outline and draw the glow line ---------- */
    function shape() {
      const w = inner.clientWidth, h = inner.clientHeight;
      if (!w || !h) return;
      const bump = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tab-bump")) || 18;
      const r = Math.min(24, (h - bump) / 2);
      const { edge, outline } = barShape(w, h, bump, r);
      $("#tabEdgePath").setAttribute("d", outline);
      $("#tabGlowPath").setAttribute("d", edge);
      $("#tabGlow").setAttribute("viewBox", `0 0 ${w} ${h}`);
      if (window.CSS && CSS.supports("clip-path", "path('M0 0')")) {
        glass.style.clipPath = `path('${outline}')`;
        glass.classList.add("has-bump");
      }
      moveDot();
    }

    /* ---------- active indicator: a small dot that slides under the current tab ---------- */
    function moveDot() {
      const t = tabOf(active);
      if (!t || t.classList.contains("tab--center") || !inner.clientWidth) { dot.classList.remove("is-on"); return; }
      const a = inner.getBoundingClientRect(), r = t.getBoundingClientRect();
      dot.style.setProperty("--x", `${Math.round(r.left - a.left + r.width / 2)}px`);
      dot.classList.add("is-on");
    }
    function setActive(name) {
      active = name;
      tabs.forEach((t) => {
        if (t.dataset.tab === name) t.setAttribute("aria-current", "page");
        else t.removeAttribute("aria-current");
      });
      moveDot();
    }

    /* ---------- hide on scroll down, show on scroll up ---------- */
    let lastY = window.scrollY, ticking = false, holdUntil = 0; // holdUntil: our own jumps never hide the bar
    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        ticking = false;
        const y = window.scrollY;
        if (!openSheet) {
          if (y > lastY + 6 && y > 140 && performance.now() > holdUntil) bar.classList.add("is-hidden");
          else if (y < lastY - 6 || y < 140) bar.classList.remove("is-hidden");
          spy();
        }
        lastY = y;
      });
    }
    function spy() {
      if (openSheet || document.body.classList.contains("is-results")) return;
      const hero = $("#top"), kids = $("#kids"), mid = window.innerHeight * 0.45;
      const inView = (n) => { if (!n) return false; const r = n.getBoundingClientRect(); return r.top < mid && r.bottom > 140; };
      setActive(hero && hero.getBoundingClientRect().bottom > mid ? "home" : inView(kids) ? "kids" : "");
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    if (window.ResizeObserver) new ResizeObserver(shape).observe(inner);
    else window.addEventListener("resize", shape, { passive: true });

    /* ---------- haptic-style press, and long-press on Home for Upcoming Trailers ---------- */
    let pressTimer = 0, longFired = false;
    bar.addEventListener("pointerdown", (e) => {
      const t = e.target.closest(".tab");
      if (!t) return;
      t.classList.add("is-pressed");
      if (navigator.vibrate && !reduce.matches) { try { navigator.vibrate(8); } catch (_) { /* unsupported */ } }
      longFired = false;
      clearTimeout(pressTimer);
      if (t.dataset.tab === "home") {
        pressTimer = setTimeout(() => {
          longFired = true;
          if (navigator.vibrate && !reduce.matches) { try { navigator.vibrate([10, 40, 14]); } catch (_) { /* */ } }
          close(false);
          setActive("home");
          jump("trailers");
        }, LONG_PRESS_MS);
      }
    });
    const release = () => { clearTimeout(pressTimer); tabs.forEach((t) => t.classList.remove("is-pressed")); };
    ["pointerup", "pointercancel", "pointerleave"].forEach((ev) => bar.addEventListener(ev, release));
    bar.addEventListener("contextmenu", (e) => { if (e.target.closest(".tab")) e.preventDefault(); });

    /* ---------- sheets ---------- */
    function focusables(root) {
      return [...root.querySelectorAll("button, [href], input, [tabindex]:not([tabindex='-1'])")].filter((n) => !n.disabled && n.offsetParent !== null);
    }
    function open(id, tabName) {
      if (openSheet) close(false);
      const sh = $(`#${id}`);
      lastFocus = document.activeElement;
      sh.hidden = false;
      openSheet = sh;
      document.body.classList.add("sheet-open");
      bar.classList.remove("is-hidden");
      setActive(tabName);
      if (TDM.hero) TDM.hero.pause("sheet");
      requestAnimationFrame(() => sh.classList.add("is-open"));
      const first = sh.querySelector("input") || sh.querySelector(".sheet__x, .sheet__close");
      if (first) first.focus({ preventScroll: true });
    }
    function close(restore = true) {
      const sh = openSheet;
      if (!sh) return;
      openSheet = null;
      sh.classList.remove("is-open");
      document.body.classList.remove("sheet-open");
      const done = () => { if (!sh.classList.contains("is-open")) sh.hidden = true; };
      if (reduce.matches) done(); else setTimeout(done, 260);
      if (TDM.hero) TDM.hero.resume("sheet");
      spy();
      if (restore && lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
    }
    document.addEventListener("click", (e) => {
      if (e.target.closest("[data-sheet-close]")) { close(); return; }
      const go = e.target.closest("[data-goto]");
      if (go) { close(false); jump(go.dataset.goto); }
      // a card inside a sheet opens the player above the sheet; closing the player returns to the sheet
    });
    document.addEventListener("keydown", (e) => {
      if (!openSheet) return;
      if (e.key === "Escape" && $("#player").hidden) { e.preventDefault(); close(); return; }
      if (e.key === "Tab") { // keep focus inside the open sheet
        const f = focusables(openSheet);
        if (!f.length) return;
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    });

    function jump(id) {
      if (TDM.hideResults) TDM.hideResults();
      holdUntil = performance.now() + 1500;
      bar.classList.remove("is-hidden");
      const behavior = reduce.matches ? "auto" : "smooth";
      if (id === "top") { window.scrollTo({ top: 0, behavior }); return; }
      const n = document.getElementById(id);
      if (n) n.scrollIntoView({ block: "start", behavior });
    }

    /* ---------- Search sheet ---------- */
    const sInput = $("#sheetSearchInput"), sGrid = $("#sheetSearchGrid"), sHint = $("#sheetSearchHint"), sCount = $("#sheetSearchCount");
    let st = 0;
    function runSearch() {
      const q = sInput.value.trim();
      sGrid.textContent = "";
      if (q.length < 2) { sHint.hidden = false; sCount.textContent = ""; return; }
      sHint.hidden = true;
      const hits = TDM.searchItems(q, TDM.catalog.videos, TDM.trailers).slice(0, 60);
      sCount.textContent = hits.length
        ? `${hits.length === 60 ? "60+" : hits.length} ${hits.length === 1 ? "result" : "results"}`
        : "Nothing matches that yet. Try another title.";
      const frag = document.createDocumentFragment();
      for (const v of hits) frag.appendChild(tile(v, { trailer: !!v.film }));
      sGrid.appendChild(frag);
    }
    sInput.maxLength = 100;
    sInput.addEventListener("input", () => { clearTimeout(st); st = setTimeout(runSearch, 140); });
    $("#sheetSearchForm").addEventListener("submit", (e) => { e.preventDefault(); runSearch(); sInput.blur(); });

    /* ---------- Browse sheet: Upcoming Trailers first, then sections and genres ---------- */
    function chip(label, id, count, cls) {
      const b = el("button", "chip" + (cls ? ` ${cls}` : ""));
      b.type = "button";
      b.dataset.goto = id;
      b.append(el("span", "", label));
      if (count != null) b.append(el("span", "chip__n", String(count)));
      return b;
    }
    const secWrap = $("#chipSections"), genWrap = $("#chipGenres");
    if (TDM.trailers.length) secWrap.appendChild(chip("Upcoming Trailers", "trailers", TDM.trailers.length, "chip--hot"));
    for (const sec of TDM.catalog.sections) {
      secWrap.appendChild(chip(sec.title, sec.id, TDM.catalog.videos.filter((v) => v.section === sec.id).length));
    }
    const genres = TDM.genreRows || [];
    for (const g of genres) genWrap.appendChild(chip(g.genre, g.id, g.count));
    if (!genres.length) { genWrap.hidden = true; genWrap.previousElementSibling.hidden = true; }

    /* ---------- My List sheet + badge ---------- */
    function renderList() {
      const ids = myList.ids();
      const grid = $("#listGrid");
      grid.textContent = "";
      $("#listEmpty").hidden = ids.length > 0;
      const frag = document.createDocumentFragment();
      for (const id of ids) {
        const v = TDM.byId.get(id);
        if (v) frag.appendChild(tile(v, { trailer: !!v.trailer, saved: true }));
      }
      grid.appendChild(frag);
    }
    function syncBadge(bump) {
      const n = myList.ids().length;
      badge.textContent = n > 99 ? "99+" : String(n);
      badge.hidden = n === 0;
      tabOf("mylist").setAttribute("aria-label", n ? `My List, ${n} saved` : "My List, empty");
      if (bump && !reduce.matches) { badge.classList.remove("is-bump"); void badge.offsetWidth; badge.classList.add("is-bump"); }
    }
    document.addEventListener("tdm:list", (e) => {
      syncBadge(e.detail.on);
      if (openSheet && openSheet.id === "sheetList") renderList();
    });
    syncBadge(false);

    /* ---------- tab actions ---------- */
    bar.addEventListener("click", (e) => {
      const t = e.target.closest(".tab");
      if (!t) return;
      const name = t.dataset.tab;
      if (name === "home") {
        if (longFired) { longFired = false; return; } // the long press already went to Upcoming Trailers
        close(false); setActive("home"); jump("top");
      } else if (name === "trailers") { close(false); setActive("trailers"); jump("trailers"); }
      else if (name === "kids") { close(false); setActive("kids"); jump($("#kids") ? "kids" : "movies"); }
      else if (name === "search") { if (openSheet && openSheet.id === "sheetSearch") close(); else open("sheetSearch", "search"); }
      else if (name === "browse") { if (openSheet && openSheet.id === "sheetGenres") close(); else open("sheetGenres", "browse"); }
      else if (name === "mylist") {
        if (openSheet && openSheet.id === "sheetList") close();
        else { renderList(); open("sheetList", "mylist"); }
      }
    });

    /* ---------- Shuffle (in the Browse sheet): a random trailer, never the one playing behind ---------- */
    function shuffle(btn) {
      const list = TDM.trailers;
      if (!list.length) return;
      if (btn && !reduce.matches) { btn.classList.remove("is-spin"); void btn.offsetWidth; btn.classList.add("is-spin"); }
      const cur = TDM.hero && TDM.hero.state ? TDM.hero.state().index : -1;
      let i = Math.floor(Math.random() * list.length);
      if (list.length > 1 && i === cur) i = (i + 1) % list.length;
      close(false);
      TDM.openPlayer(list[i].id);
    }
    document.addEventListener("click", (e) => { const b = e.target.closest("[data-shuffle]"); if (b) shuffle(b); });
    // No Kids section in this catalog: the slot becomes Upcoming Trailers instead.
    if (!$("#kids") && tabOf("kids")) {
      const k = tabOf("kids");
      k.dataset.tab = "trailers";
      k.querySelector(".tab__label").textContent = "Trailers";
    }

    phone.addEventListener("change", () => { if (!phone.matches) close(false); shape(); });
    spy();
    requestAnimationFrame(shape);
    TDM.tabbar = {
      open, close, setActive,
      state: () => ({ active, sheet: openSheet && openSheet.id, hidden: bar.classList.contains("is-hidden"), badge: badge.hidden ? 0 : badge.textContent,
        bump: glass.classList.contains("has-bump") }),
    };
  }

  document.addEventListener("tdm:ready", init);
})();
