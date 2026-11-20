/* 2DayMovie header carousel: muted, looping official trailer clips that slide
   (or crossfade with prefers-reduced-motion) into each other. Auto-advances,
   preloads the neighbouring players, supports swipe, arrows, dots and keys.

   The control bar (#heroBar) is server-rendered in templates/index.html so it
   is present and labelled before any script runs; this file wires it up:

     #heroPause          play / pause the carousel          (Space or K)
     #heroMute           sound switch, muted by default      (M)
     #heroVolume         volume slider (hover / focus / tap)
     #heroBrightPresets  Dim / Normal / Bright radiogroup    (B cycles)
     #heroBrightness     fine brightness slider
     #heroSizes          Compact / Standard / Full radiogroup
     #heroFullscreen     Fullscreen API on the hero          (F, Esc exits)

   Sound, volume, brightness and size are remembered in localStorage.
   YouTube's own chrome stays hidden: the iframes are sandboxed, unfocusable
   and pointer-events: none, and are driven only through the IFrame API.
*/
(() => {
  "use strict";
  const SLIDE_MS = 30000; // default auto-advance when a clip has no start/end
  const STORE_KEY = "tdm.hero.v2"; // v2: Full is the default size; v1 sizes are ignored
  const LEGACY_KEY = "tdm.hero.v1";
  const FADE_MS = 650;    // sound fade in / out
  const BRIGHT = { dim: 0.65, normal: 1, bright: 1.3 };
  const BRIGHT_ORDER = ["dim", "normal", "bright"];
  const SIZES = ["compact", "standard", "full"];
  const SIZE_NAMES = { compact: "Compact", standard: "Standard", full: "Full" };
  const TDM = (window.TDM = window.TDM || {});
  let $, el, svg, thumb, fmtDate, loadYT, openPlayer, embedFrame, ICON_PLAY, ICON_INFO, NOCOOKIE, reduceMotion, trailers;

  function durationOf(t) {
    const start = Number(t && t.clip_start);
    const end = Number(t && t.clip_end);
    if (Number.isFinite(start) && Number.isFinite(end) && end > start) {
      return Math.min(45, Math.max(20, end - start)) * 1000;
    }
    return SLIDE_MS;
  }

  const prefs = {
    load() {
      try { localStorage.removeItem(LEGACY_KEY); } catch (_) { /* private mode */ }
      try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch (_) { return {}; }
    },
    save(patch) {
      try { localStorage.setItem(STORE_KEY, JSON.stringify({ ...prefs.load(), ...patch })); } catch (_) { /* private mode */ }
    },
  };

  function daysUntil(iso) {
    const ms = new Date(iso + "T12:00:00") - new Date();
    return Math.ceil(ms / 86400000);
  }

  /* ---------------- hero carousel ---------------- */
  function makeHero() {
    const track = $("#heroTrack");
    const content = $("#heroContent");
    const dots = $("#heroDots");
    const bar = $("#heroProgress");
    const heroEl = $("#top");
    const slides = [];
    const players = new Map(); // index -> { player, ready, fade }
    const holds = new Set();
    let cur = 0, busy = false, started = 0, remaining = SLIDE_MS, total = SLIDE_MS, raf = 0, timer = 0, YTlib = null;

    const saved = prefs.load();
    let soundOn = false;                       // always start muted (autoplay rules)
    let soundWanted = saved.sound === true;    // re-enabled on the first user gesture
    let volume = Number.isFinite(saved.volume) ? Math.min(100, Math.max(0, saved.volume)) : 60;
    let brightness = Number.isFinite(saved.brightness) ? Math.min(1.6, Math.max(0.4, saved.brightness)) : 1;
    let size = SIZES.includes(saved.size) ? saved.size : "full";

    const ui = {};

    function build() {
      trailers.forEach((t, i) => {
        const s = el("div", "slide");
        s.setAttribute("role", "group");
        s.setAttribute("aria-roledescription", "slide");
        s.setAttribute("aria-label", `${i + 1} of ${trailers.length}: ${t.film}`);
        s.setAttribute("aria-hidden", i === 0 ? "false" : "true");
        const poster = el("img", "slide__poster");
        poster.alt = "";
        // 640px poster for phones, 1280px for larger screens; hqdefault if a size is missing.
        poster.srcset = `${thumb(t.id, "sddefault")} 640w, ${thumb(t.id, "maxresdefault")} 1280w`;
        poster.sizes = "100vw";
        poster.src = thumb(t.id, "maxresdefault");
        poster.addEventListener("error", () => { poster.srcset = ""; poster.src = thumb(t.id, "hqdefault"); }, { once: true });
        if (i === 0) poster.fetchPriority = "high";
        if (i > 1) poster.loading = "lazy";
        const vid = el("div", "slide__video");
        vid.appendChild(el("div"));
        s.append(poster, vid);
        track.appendChild(s);
        slides.push(s);
        const d = el("button", "hero__dot");
        d.type = "button";
        d.setAttribute("role", "tab");
        d.setAttribute("aria-label", `Show ${t.film} trailer`);
        d.addEventListener("click", () => go(i, i > cur ? 1 : -1, true));
        dots.appendChild(d);
      });
      if (!slides.length) { heroEl.hidden = true; return; }
      slides[0].classList.add("is-current");
      paint();
      bind();
      buildTools();
      if (reduceMotion.matches) return; // static thumbnails only: no autoplay, no auto-advance
      startTimer(durationOf(trailers[0]));
      // Live background: muted trailers start on load, no click needed.
      loadYT().then((YT) => { YTlib = YT; warm(); }).catch(() => {}); // posters stay up if the API fails
    }

    function paint() {
      const t = trailers[cur];
      content.textContent = "";
      content.appendChild(el("span", "hero__tag", "Upcoming trailer"));
      // Logo-style title: "Avengers: Doomsday" -> big AVENGERS over a spaced DOOMSDAY.
      const h = el("h1", "hero__title hero__logo");
      const cut = t.film.indexOf(": ");
      if (cut > 0) {
        h.append(el("span", "hero__logo-main", t.film.slice(0, cut)), el("span", "sr", ": "),
          el("span", "hero__logo-sub", t.film.slice(cut + 2)));
      } else {
        h.appendChild(el("span", "hero__logo-main", t.film));
      }
      content.appendChild(h);
      const date = el("p", "hero__date");
      date.appendChild(el("span", "hero__date-label", "In cinemas"));
      const time = el("time", "hero__date-value", fmtDate(t.release));
      time.dateTime = t.release;
      date.appendChild(time);
      const days = daysUntil(t.release);
      if (days > 0 && days <= 365) date.appendChild(el("span", "hero__date-count", days === 1 ? "Tomorrow" : `in ${days} days`));
      content.appendChild(date);
      const actions = el("div", "hero__actions");
      const play = el("button", "btn btn--play");
      play.type = "button";
      play.append(svg(ICON_PLAY), document.createTextNode("Watch trailer"));
      play.addEventListener("click", () => openPlayer(t.id));
      const more = el("a", "btn btn--ghost");
      more.href = "#trailers";
      more.append(svg(ICON_INFO), document.createTextNode("All trailers"));
      actions.append(play, more);
      content.appendChild(actions);
      [...dots.children].forEach((d, i) => {
        d.setAttribute("aria-selected", String(i === cur));
        d.style.setProperty("--p", i === cur && reduceMotion.matches ? "1" : "0");
      });
      // On phones the dots are one scrollable line: keep the current one in view.
      const cd = dots.children[cur];
      if (cd && dots.scrollWidth > dots.clientWidth) {
        dots.scrollLeft = Math.max(0, cd.offsetLeft - dots.clientWidth / 2 + cd.offsetWidth / 2);
      }
      slides.forEach((s, i) => s.setAttribute("aria-hidden", String(i !== cur)));
    }

    const mod = (i) => (i + slides.length) % slides.length;

    /* ---------- sound: mute / unMute / setVolume through the IFrame API ---------- */
    function fadeTo(entry, to, done) {
      if (!entry || !entry.ready) { if (done) done(); return; }
      cancelAnimationFrame(entry.fade);
      const p = entry.player;
      let from = 0;
      try { from = p.isMuted() ? 0 : p.getVolume(); } catch (_) { /* not ready */ }
      const t0 = performance.now();
      const step = (now) => {
        const k = Math.min(1, (now - t0) / FADE_MS);
        const v = Math.round(from + (to - from) * (k * (2 - k))); // ease-out
        try { p.setVolume(v); } catch (_) { return; }
        if (k < 1) entry.fade = requestAnimationFrame(step);
        else if (done) done();
      };
      entry.fade = requestAnimationFrame(step);
    }

    // Bring a player's audio to the current state; fade unless told to snap.
    function applyMute(entry, snap) {
      if (!entry || !entry.ready) return;
      const p = entry.player;
      try {
        if (soundOn && entry.wantPlay) {
          if (snap) { p.setVolume(volume); p.unMute(); return; }
          if (p.isMuted()) { p.setVolume(0); p.unMute(); }
          fadeTo(entry, volume);
        } else if (snap) {
          cancelAnimationFrame(entry.fade);
          p.mute();
        } else {
          fadeTo(entry, 0, () => { try { p.mute(); } catch (_) { /* gone */ } });
        }
      } catch (_) { /* player not ready */ }
    }

    function setSound(on, opts = {}) {
      if (on && volume === 0) { volume = 60; prefs.save({ volume }); }
      soundOn = !!on;
      if (!opts.keepWish) soundWanted = soundOn;
      if (!opts.noSave) prefs.save({ sound: soundOn });
      syncSound();
      applyMute(players.get(cur));
    }

    function setVolume(v) {
      volume = Math.round(Math.min(100, Math.max(0, v)));
      prefs.save({ volume });
      if (volume === 0 && soundOn) { setSound(false); return; }
      if (volume > 0 && !soundOn) { setSound(true); return; }
      syncSound();
      const e = players.get(cur);
      if (e && e.ready && soundOn) { cancelAnimationFrame(e.fade); try { e.player.setVolume(volume); } catch (_) { /* */ } }
    }

    function syncSound() {
      ui.mute.setAttribute("aria-pressed", String(soundOn));
      ui.mute.setAttribute("aria-label", soundOn ? "Mute trailer" : "Unmute trailer");
      ui.mute.dataset.tip = soundOn ? "Mute (M)" : "Unmute (M)";
      ui.vol.value = String(volume);
      ui.vol.setAttribute("aria-valuetext", soundOn ? `${volume}%` : `${volume}%, muted`);
      ui.vol.style.setProperty("--fill", `${volume}%`);
      heroEl.classList.toggle("is-sound", soundOn);
    }

    /* ---------- brightness ---------- */
    const levelOf = (b) => BRIGHT_ORDER.find((k) => Math.abs(BRIGHT[k] - b) < 0.001) || null;
    function setBrightness(b, save = true) {
      brightness = Math.round(Math.min(1.6, Math.max(0.4, b)) * 100) / 100;
      heroEl.style.setProperty("--hero-brightness", String(brightness));
      ui.bright.value = String(brightness);
      ui.bright.setAttribute("aria-valuetext", `${Math.round(brightness * 100)}%`);
      ui.bright.style.setProperty("--fill", `${((brightness - 0.4) / 1.2) * 100}%`);
      const level = levelOf(brightness);
      selectRadio(ui.brightRadios, level);
      const name = level ? level[0].toUpperCase() + level.slice(1) : `${Math.round(brightness * 100)}%`;
      ui.brightLabel.textContent = name;
      ui.brightCycle.setAttribute("aria-label", `Brightness: ${name}. Change brightness`);
      if (save) prefs.save({ brightness });
    }
    function cycleBrightness() {
      const level = levelOf(brightness);
      const i = level ? BRIGHT_ORDER.indexOf(level) : (brightness < 1 ? 0 : 2);
      setBrightness(BRIGHT[BRIGHT_ORDER[(i + 1) % BRIGHT_ORDER.length]]);
    }

    /* ---------- size + fullscreen ---------- */
    function setSize(next, save = true) {
      size = SIZES.includes(next) ? next : "full";
      heroEl.dataset.size = size;
      selectRadio(ui.sizeRadios, size);
      ui.sizeLabel.textContent = SIZE_NAMES[size];
      ui.sizeCycle.setAttribute("aria-label", `Video size: ${SIZE_NAMES[size]}. Change size`);
      if (save) prefs.save({ size });
    }
    const fsElement = () => document.fullscreenElement || document.webkitFullscreenElement || null;
    const fsEnabled = () => !!(document.fullscreenEnabled || document.webkitFullscreenEnabled);
    function toggleFullscreen() {
      if (fsElement() === heroEl) {
        (document.exitFullscreen || document.webkitExitFullscreen).call(document);
      } else if (fsEnabled()) {
        const req = heroEl.requestFullscreen || heroEl.webkitRequestFullscreen;
        const r = req.call(heroEl, { navigationUI: "hide" });
        if (r && r.catch) r.catch(() => {});
      }
    }
    function syncFullscreen() {
      const on = fsElement() === heroEl;
      heroEl.classList.toggle("is-fullscreen", on);
      ui.fs.setAttribute("aria-pressed", String(on));
      ui.fs.setAttribute("aria-label", on ? "Exit fullscreen" : "Enter fullscreen");
      ui.fs.dataset.tip = on ? "Exit fullscreen (F / Esc)" : "Fullscreen (F)";
    }

    /* ---------- radiogroups (roving tabindex) ---------- */
    function selectRadio(radios, value) {
      let any = false;
      radios.forEach((r) => {
        const on = (r.dataset.level || r.dataset.size) === value;
        any = any || on;
        r.setAttribute("aria-checked", String(on));
        r.tabIndex = on ? 0 : -1;
      });
      if (!any && radios[0]) radios[1 % radios.length].tabIndex = 0; // custom value: keep one tab stop
    }
    function wireRadios(radios, pick) {
      radios.forEach((r, i) => {
        r.addEventListener("click", () => pick(r));
        r.addEventListener("keydown", (e) => {
          const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
          if (!d) return;
          e.preventDefault();
          e.stopPropagation();
          const n = radios[(i + d + radios.length) % radios.length];
          pick(n);
          n.focus();
        });
      });
    }

    /* ---------- players ---------- */
    function ensurePlayer(i) {
      if (!YTlib || players.has(i) || reduceMotion.matches) return;
      const t = trailers[i];
      const box = slides[i].querySelector(".slide__video");
      const mount = box.firstElementChild;
      const start = t.clip_start || 0;
      const end = t.clip_end || start + 32;
      const entry = { player: null, ready: false, wantPlay: i === cur, fade: 0 };
      players.set(i, entry);
      // Build the sandboxed nocookie iframe ourselves, then let the IFrame API attach to it.
      const frame = embedFrame(t.id, {
        // no YouTube chrome in the header: our control bar is the only control surface
        autoplay: i === cur ? 1 : 0, mute: 1, controls: 0, disablekb: 1, fs: 0, rel: 0, playsinline: 1,
        modestbranding: 1, iv_load_policy: 3, cc_load_policy: 0, showinfo: 0, start, end,
      }, `${t.film} trailer clip`);
      frame.tabIndex = -1;
      frame.setAttribute("aria-hidden", "true");
      frame.style.pointerEvents = "none"; // clicks/taps never reach YouTube's own overlay
      mount.replaceWith(frame);
      entry.player = new YTlib.Player(frame, {
        events: {
          onReady: (e) => {
            entry.ready = true;
            e.target.mute(); // start silent; applyMute fades in for the current slide
            e.target.playVideo(); // buffer the first frames even for the preloaded neighbour
          },
          onStateChange: (e) => {
            const S = YTlib.PlayerState;
            if (e.data === S.PLAYING) {
              if (!entry.wantPlay || holds.size) { e.target.mute(); e.target.pauseVideo(); return; } // parked
              applyMute(entry);
              box.classList.add("is-playing");
              slides[i].classList.add("has-video");
            } else if (e.data === S.ENDED) {
              e.target.seekTo(start, true); // loop the clip from start to end
              if (entry.wantPlay) e.target.playVideo();
            }
          },
          onError: () => { box.classList.remove("is-playing"); slides[i].classList.remove("has-video"); },
        },
      });
      // The API may swap in its own element; keep the sandbox and focus rules on whatever iframe is live.
      const live = box.querySelector("iframe");
      if (live && live !== frame) {
        live.setAttribute("sandbox", TDM.SANDBOX);
        live.tabIndex = -1;
        live.setAttribute("aria-hidden", "true");
        live.style.pointerEvents = "none";
      }
    }

    function playAt(i) {
      const p = players.get(i);
      if (!p) return;
      p.wantPlay = true;
      if (p.ready && !holds.size) {
        p.player.playVideo();
        applyMute(p);
      }
    }
    function pauseAt(i) {
      const p = players.get(i);
      if (!p) return;
      p.wantPlay = false;
      if (p.ready) { applyMute(p, true); p.player.pauseVideo(); }
    }

    // Keep the current slide and both neighbours loaded; drop the rest.
    function warm() {
      if (!YTlib || reduceMotion.matches) return;
      const keep = new Set([cur, mod(cur + 1), mod(cur - 1)]);
      for (const [i, p] of players) {
        if (!keep.has(i)) {
          cancelAnimationFrame(p.fade);
          try { p.player.destroy(); } catch (_) { /* already gone */ }
          players.delete(i);
          const box = slides[i].querySelector(".slide__video");
          box.classList.remove("is-playing");
          slides[i].classList.remove("has-video");
          box.textContent = "";
          box.appendChild(el("div"));
        }
      }
      ensurePlayer(cur);
      playAt(cur);
      ensurePlayer(mod(cur + 1));
      ensurePlayer(mod(cur - 1));
    }

    function go(target, dir, manual) {
      target = mod(target);
      if (busy || target === cur || slides.length < 2) return;
      busy = true;
      const from = slides[cur], to = slides[target];
      const prevIndex = cur;
      const prev = players.get(prevIndex);
      if (prev) { prev.wantPlay = false; applyMute(prev); } // fade the outgoing clip's audio
      cur = target;
      if (!reduceMotion.matches) {
        ensurePlayer(target);
        playAt(target);
      }
      const fade = reduceMotion.matches;
      to.classList.remove("anim");
      to.classList.add("is-moving");
      if (fade) { to.style.opacity = "0"; to.style.zIndex = "3"; }
      else to.style.transform = `translate3d(${dir > 0 ? 100 : -100}%,0,0)`;
      void to.offsetWidth; // commit the start position before animating
      from.classList.add("anim");
      to.classList.add("anim");
      if (fade) { to.style.opacity = "1"; }
      else {
        to.style.transform = "translate3d(0,0,0)";
        from.style.transform = `translate3d(${dir > 0 ? -100 : 100}%,0,0)`;
      }
      paint();
      startTimer(durationOf(trailers[cur])); // manual or automatic move: restart the countdown
      const ms = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--slide-ms")) || 750;
      setTimeout(() => {
        from.classList.remove("is-current", "anim");
        from.style.transform = "";
        from.style.opacity = "";
        to.classList.remove("is-moving", "anim");
        to.classList.add("is-current");
        to.style.transform = "";
        to.style.opacity = "";
        to.style.zIndex = "";
        if (prevIndex !== cur) pauseAt(prevIndex);
        busy = false;
        warm();
      }, fade ? 0 : ms + 40);
      if (manual) dots.children[cur].focus({ preventScroll: true });
    }

    function tick() {
      const left = Math.max(0, remaining - (performance.now() - started));
      const frac = 1 - left / total;
      bar.style.width = `${frac * 100}%`;
      const d = dots.children[cur];
      if (d) d.style.setProperty("--p", frac.toFixed(4)); // slim per-slide progress in the active dot
      if (left <= 0) { go(cur + 1, 1, false); return; }
      raf = requestAnimationFrame(tick);
    }
    function startTimer(ms) {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
      remaining = ms;
      total = ms;
      started = performance.now();
      if (bar) bar.style.width = "0%";
      if (reduceMotion.matches) return; // no auto-advance
      if (!holds.size) raf = requestAnimationFrame(tick);
    }
    function pause(reason) {
      if (!slides.length) return;
      if (reason === "modal" && fsElement() === heroEl) toggleFullscreen(); // the player opens outside the hero
      if (!holds.size) {
        remaining = Math.max(0, remaining - (performance.now() - started));
        cancelAnimationFrame(raf);
        const p = players.get(cur);
        if (p && p.ready) { applyMute(p, true); p.player.pauseVideo(); }
      }
      holds.add(reason);
      syncPause();
    }
    function resume(reason) {
      if (!slides.length || !holds.has(reason)) return;
      holds.delete(reason);
      syncPause();
      if (holds.size) return;
      started = performance.now();
      if (!reduceMotion.matches) raf = requestAnimationFrame(tick);
      const p = players.get(cur);
      if (p && p.ready && p.wantPlay) {
        p.player.playVideo();
        applyMute(p);
      }
    }
    function syncPause() {
      if (!ui.pause) return;
      const paused = holds.has("user");
      ui.pause.setAttribute("aria-pressed", String(paused));
      ui.pause.setAttribute("aria-label", paused ? "Play trailers" : "Pause trailers");
      ui.pause.dataset.tip = paused ? "Play (Space / K)" : "Pause (Space / K)";
      heroEl.classList.toggle("is-paused", paused);
    }
    const togglePause = () => (holds.has("user") ? resume("user") : pause("user"));

    /* ---------- control bar ---------- */
    function buildTools() {
      ui.barEl = $("#heroBar");
      ui.pause = $("#heroPause");
      ui.mute = $("#heroMute");
      ui.vol = $("#heroVolume");
      ui.soundGroup = $("#heroSoundGroup");
      ui.bright = $("#heroBrightness");
      ui.brightRadios = [...document.querySelectorAll("#heroBrightPresets [role=radio]")];
      ui.brightCycle = $("#heroBrightCycle");
      ui.brightLabel = $("#heroBrightLabel");
      ui.sizeRadios = [...document.querySelectorAll("#heroSizes [role=radio]")];
      ui.sizeCycle = $("#heroSizeCycle");
      ui.sizeLabel = $("#heroSizeLabel");
      ui.fs = $("#heroFullscreen");
      if (!ui.barEl) return;

      track.classList.add("is-dimmable");
      if (reduceMotion.matches) {
        // Static posters only: no clip to pause or hear.
        ui.pause.hidden = true;
        ui.soundGroup.hidden = true;
        ui.barEl.classList.add("is-static");
      }
      if (!fsEnabled()) ui.fs.hidden = true;

      ui.pause.addEventListener("click", togglePause);
      ui.mute.addEventListener("click", () => setSound(!soundOn));
      ui.vol.addEventListener("input", () => { setVolume(Number(ui.vol.value)); keepVolOpen(); });
      ui.bright.addEventListener("input", () => setBrightness(Number(ui.bright.value)));
      ui.brightCycle.addEventListener("click", cycleBrightness);
      ui.sizeCycle.addEventListener("click", () => setSize(SIZES[(SIZES.indexOf(size) + 1) % SIZES.length]));
      ui.fs.addEventListener("click", toggleFullscreen);
      wireRadios(ui.brightRadios, (r) => setBrightness(BRIGHT[r.dataset.level]));
      wireRadios(ui.sizeRadios, (r) => setSize(r.dataset.size));
      document.addEventListener("fullscreenchange", syncFullscreen);
      document.addEventListener("webkitfullscreenchange", syncFullscreen);

      // Volume slider: hover / focus on desktop (CSS), tap to open on touch screens.
      let volTimer = 0;
      function keepVolOpen() {
        if (!ui.soundGroup.classList.contains("is-open")) return;
        clearTimeout(volTimer);
        volTimer = setTimeout(() => ui.soundGroup.classList.remove("is-open"), 3500);
      }
      ui.mute.addEventListener("pointerup", (e) => {
        if (e.pointerType !== "touch" && e.pointerType !== "pen") return;
        ui.soundGroup.classList.add("is-open");
        keepVolOpen();
      });
      document.addEventListener("pointerdown", (e) => {
        if (!ui.soundGroup.contains(e.target)) ui.soundGroup.classList.remove("is-open");
      });

      // A remembered "sound on" waits for the first gesture (browsers block unmuted autoplay).
      if (soundWanted && !reduceMotion.matches) {
        ui.mute.classList.add("is-armed");
        const arm = (e) => {
          window.removeEventListener("pointerdown", arm, true);
          window.removeEventListener("keydown", arm, true);
          ui.mute.classList.remove("is-armed");
          if (ui.mute.contains(e.target) || ui.soundGroup.contains(e.target)) return; // the click decides
          if (soundWanted && !soundOn) setSound(true);
        };
        window.addEventListener("pointerdown", arm, true);
        window.addEventListener("keydown", arm, true);
      }

      syncSound();
      setBrightness(brightness, false);
      setSize(size, false);
      syncFullscreen();
      syncPause();
      requestAnimationFrame(() => heroEl.classList.add("is-ready")); // enable size transitions after first paint
    }

    // Global shortcuts: M mute, B brightness, F fullscreen, Space / K pause.
    function onShortcut(e) {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) && t.type !== "range")) return;
      if (document.body.classList.contains("modal-open") || document.body.classList.contains("is-results")) return;
      if (heroEl.hidden) return;
      const r = heroEl.getBoundingClientRect();
      if (r.bottom < 80 || r.top > innerHeight - 80) return; // hero must be on screen
      const k = e.key.toLowerCase();
      if (k === "m" && !reduceMotion.matches) setSound(!soundOn);
      else if (k === "b") cycleBrightness();
      else if (k === "f" && fsEnabled()) toggleFullscreen();
      else if ((k === "k" || (k === " " && !(t && t.closest && t.closest("button, a, input")))) && !reduceMotion.matches) togglePause();
      else return;
      e.preventDefault();
    }

    function bind() {
      $("#heroPrev").addEventListener("click", () => go(cur - 1, -1, true));
      $("#heroNext").addEventListener("click", () => go(cur + 1, 1, true));
      let x0 = null, y0 = 0, id = null;
      heroEl.addEventListener("pointerdown", (e) => {
        if (e.target.closest("button, a, input, label, .hero__bar")) return;
        x0 = e.clientX; y0 = e.clientY; id = e.pointerId;
      });
      heroEl.addEventListener("pointerup", (e) => {
        if (x0 == null || e.pointerId !== id) return;
        const dx = e.clientX - x0, dy = e.clientY - y0;
        x0 = null;
        if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.3) go(cur + (dx < 0 ? 1 : -1), dx < 0 ? 1 : -1, true);
      });
      heroEl.addEventListener("pointercancel", () => { x0 = null; });
      heroEl.addEventListener("keydown", (e) => {
        if (e.target.closest(".hero__bar")) return; // sliders and radiogroups use the arrow keys
        if (e.key === "ArrowLeft") go(cur - 1, -1, true);
        if (e.key === "ArrowRight") go(cur + 1, 1, true);
      });
      document.addEventListener("keydown", onShortcut);
      document.addEventListener("visibilitychange", () => (document.hidden ? pause("hidden") : resume("hidden")));
    }

    // Read-only snapshot for QA: proves the IFrame API calls reach the sandboxed player.
    function state() {
      const e = players.get(cur);
      let muted = null, vol = null, playerState = null, currentTime = null;
      if (e && e.ready) {
        try {
          muted = e.player.isMuted(); vol = e.player.getVolume();
          playerState = e.player.getPlayerState(); currentTime = e.player.getCurrentTime();
        } catch (_) { /* */ }
      }
      return { index: cur, soundOn, volume, brightness, size, paused: holds.has("user"),
        fullscreen: fsElement() === heroEl, playerMuted: muted, playerVolume: vol, playerState, currentTime };
    }

    return { build, pause, resume, state };
  }

  document.addEventListener("tdm:ready", () => {
    ({ $, el, svg, thumb, fmtDate, loadYT, openPlayer, embedFrame, ICON_PLAY, ICON_INFO, NOCOOKIE, reduceMotion } = TDM);
    trailers = TDM.trailers;
    const hero = makeHero();
    TDM.hero = hero;
    hero.build();
  });
})();
