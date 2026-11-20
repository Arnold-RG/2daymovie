/* 2DayMovie header carousel: muted, looping official trailer clips that slide
   (or crossfade with prefers-reduced-motion) into each other. Auto-advances,
   preloads the neighbouring players, supports swipe, arrows, dots and keys.

   Hooks (owned by templates/ + static/css/; this file fills them, and injects
   sound + brightness controls that CSS does not style yet):

     <section class="hero" id="top" aria-roledescription="carousel"
              aria-label="Upcoming movie trailers">
       <div class="hero__track" id="heroTrack"></div>
       <div class="hero__shade"></div>
       <div class="hero__content" id="heroContent" aria-live="polite"></div>
       <button class="hero__arrow hero__arrow--prev" id="heroPrev"></button>
       <button class="hero__arrow hero__arrow--next" id="heroNext"></button>
       <div class="hero__dots" id="heroDots" role="tablist"></div>
       <div class="hero__progress"><span id="heroProgress"></span></div>
     </section>

   Slides use .slide / .slide__poster / .slide__video and .is-current /
   .is-moving / .is-playing / .anim (existing CSS).

   Injected controls for Forge to style:
     .hero__tools          wrapper (bottom-right is a good default)
     .hero__sound          toggle button; aria-pressed is true when sound is on
     .hero__brightness     labelled range; sets --hero-brightness on .hero
     .hero__brightness-label
     .hero__brightness-input
*/
(() => {
  "use strict";
  const SLIDE_MS = 30000; // default auto-advance when a clip has no start/end
  const TDM = (window.TDM = window.TDM || {});
  let $, el, svg, thumb, fmtDate, loadYT, openPlayer, ICON_PLAY, ICON_INFO, NOCOOKIE, reduceMotion, trailers;

  function durationOf(t) {
    const start = Number(t && t.clip_start);
    const end = Number(t && t.clip_end);
    if (Number.isFinite(start) && Number.isFinite(end) && end > start) {
      return Math.min(45, Math.max(20, end - start)) * 1000;
    }
    return SLIDE_MS;
  }

  /* ---------------- hero carousel ---------------- */
  function makeHero() {
    const track = $("#heroTrack");
    const content = $("#heroContent");
    const dots = $("#heroDots");
    const bar = $("#heroProgress");
    const heroEl = $("#top");
    const slides = [];
    const players = new Map(); // index -> { player, ready }
    const holds = new Set();
    let cur = 0, busy = false, started = 0, remaining = SLIDE_MS, total = SLIDE_MS, raf = 0, timer = 0, YTlib = null;
    let soundOn = false, soundBtn = null;

    function build() {
      trailers.forEach((t, i) => {
        const s = el("div", "slide");
        s.setAttribute("role", "group");
        s.setAttribute("aria-roledescription", "slide");
        s.setAttribute("aria-label", `${i + 1} of ${trailers.length}: ${t.film}`);
        s.setAttribute("aria-hidden", i === 0 ? "false" : "true");
        const poster = el("img", "slide__poster");
        poster.alt = "";
        poster.src = thumb(t.id, "maxresdefault");
        poster.addEventListener("error", () => { poster.src = thumb(t.id, "hqdefault"); }, { once: true });
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
      loadYT().then((YT) => { YTlib = YT; warm(); }).catch(() => {}); // posters stay up if the API fails
      startTimer(durationOf(trailers[0]));
    }

    function paint() {
      const t = trailers[cur];
      content.textContent = "";
      content.appendChild(el("span", "hero__tag", "Upcoming trailer"));
      content.appendChild(el("h1", "hero__title", t.film));
      content.appendChild(el("p", "hero__date", `In cinemas ${fmtDate(t.release)}`));
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
      [...dots.children].forEach((d, i) => d.setAttribute("aria-selected", String(i === cur)));
      slides.forEach((s, i) => s.setAttribute("aria-hidden", String(i !== cur)));
    }

    const mod = (i) => (i + slides.length) % slides.length;

    function applyMute(player) {
      if (!player) return;
      try {
        if (soundOn) player.unMute();
        else player.mute();
      } catch (_) { /* player not ready */ }
    }

    function ensurePlayer(i) {
      if (!YTlib || players.has(i) || reduceMotion.matches) return;
      const t = trailers[i];
      const box = slides[i].querySelector(".slide__video");
      const mount = box.firstElementChild;
      const start = t.clip_start || 0;
      const end = t.clip_end || start + 32;
      const entry = { player: null, ready: false, wantPlay: i === cur };
      players.set(i, entry);
      entry.player = new YTlib.Player(mount, {
        host: NOCOOKIE, videoId: t.id, width: "100%", height: "100%",
        playerVars: {
          autoplay: 0, mute: 1, controls: 0, disablekb: 1, fs: 0, rel: 0, playsinline: 1,
          modestbranding: 1, iv_load_policy: 3, start, end, origin: location.origin,
        },
        events: {
          onReady: (e) => {
            entry.ready = true;
            if (entry.wantPlay) applyMute(e.target);
            else e.target.mute(); // never leak sound from a preloaded neighbour
            e.target.playVideo(); // buffer the first frames even for the preloaded neighbour
          },
          onStateChange: (e) => {
            const S = YTlib.PlayerState;
            if (e.data === S.PLAYING) {
              if (!entry.wantPlay) { e.target.mute(); e.target.pauseVideo(); return; } // preloaded and parked
              applyMute(e.target);
              box.classList.add("is-playing");
            } else if (e.data === S.ENDED) {
              e.target.seekTo(start, true); // loop the clip from start to end
              if (entry.wantPlay) e.target.playVideo();
            }
          },
          onError: () => box.classList.remove("is-playing"), // fall back to the static thumbnail
        },
      });
      const iframe = box.querySelector("iframe");
      if (iframe) { iframe.tabIndex = -1; iframe.setAttribute("aria-hidden", "true"); }
    }

    function playAt(i) {
      const p = players.get(i);
      if (!p) return;
      p.wantPlay = true;
      if (p.ready && !holds.size) {
        applyMute(p.player);
        p.player.playVideo();
      }
    }
    function pauseAt(i) {
      const p = players.get(i);
      if (!p) return;
      p.wantPlay = false;
      if (p.ready) p.player.pauseVideo();
    }

    // Keep the current slide and both neighbours loaded; drop the rest.
    function warm() {
      if (!YTlib || reduceMotion.matches) return;
      const keep = new Set([cur, mod(cur + 1), mod(cur - 1)]);
      for (const [i, p] of players) {
        if (!keep.has(i)) {
          try { p.player.destroy(); } catch (_) { /* already gone */ }
          players.delete(i);
          const box = slides[i].querySelector(".slide__video");
          box.classList.remove("is-playing");
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
      cur = target;
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
        pauseAt(prevIndex);
        busy = false;
        warm();
      }, fade ? 0 : ms + 40);
      if (manual) dots.children[cur].focus({ preventScroll: true });
    }

    function tick() {
      const left = Math.max(0, remaining - (performance.now() - started));
      bar.style.width = `${(1 - left / total) * 100}%`;
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
      if (!holds.size) {
        remaining = Math.max(0, remaining - (performance.now() - started));
        cancelAnimationFrame(raf);
        const p = players.get(cur);
        if (p && p.ready) p.player.pauseVideo();
      }
      holds.add(reason);
    }
    function resume(reason) {
      if (!slides.length || !holds.has(reason)) return;
      holds.delete(reason);
      if (holds.size) return;
      started = performance.now();
      if (!reduceMotion.matches) raf = requestAnimationFrame(tick);
      const p = players.get(cur);
      if (p && p.ready && p.wantPlay) {
        applyMute(p.player);
        p.player.playVideo();
      }
    }

    function syncSoundButton() {
      if (!soundBtn) return;
      soundBtn.setAttribute("aria-pressed", String(soundOn));
      soundBtn.setAttribute("aria-label", soundOn ? "Mute trailer" : "Unmute trailer");
    }

    function toggleSound() {
      soundOn = !soundOn;
      syncSoundButton();
      const p = players.get(cur);
      if (p && p.ready) applyMute(p.player);
    }

    function buildTools() {
      const tools = el("div", "hero__tools");
      soundBtn = el("button", "hero__sound");
      soundBtn.type = "button";
      soundBtn.setAttribute("aria-pressed", "false");
      soundBtn.setAttribute("aria-label", "Unmute trailer");
      soundBtn.textContent = "Sound";
      soundBtn.addEventListener("click", toggleSound);

      const brightness = el("div", "hero__brightness");
      const label = el("label", "hero__brightness-label", "Brightness");
      label.setAttribute("for", "heroBrightness");
      const input = el("input", "hero__brightness-input");
      input.type = "range";
      input.id = "heroBrightness";
      input.min = "0.5";
      input.max = "1.5";
      input.step = "0.05";
      input.value = "1";
      input.setAttribute("aria-valuemin", "0.5");
      input.setAttribute("aria-valuemax", "1.5");
      heroEl.style.setProperty("--hero-brightness", "1");
      track.style.filter = "brightness(var(--hero-brightness, 1))";
      input.addEventListener("input", () => {
        heroEl.style.setProperty("--hero-brightness", input.value);
      });
      brightness.append(label, input);
      tools.append(soundBtn, brightness);
      heroEl.appendChild(tools);
    }

    function bind() {
      $("#heroPrev").addEventListener("click", () => go(cur - 1, -1, true));
      $("#heroNext").addEventListener("click", () => go(cur + 1, 1, true));
      let x0 = null, y0 = 0, id = null;
      heroEl.addEventListener("pointerdown", (e) => {
        if (e.target.closest("button, a, input, label")) return;
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
        if (e.key === "ArrowLeft") go(cur - 1, -1, true);
        if (e.key === "ArrowRight") go(cur + 1, 1, true);
      });
      document.addEventListener("visibilitychange", () => (document.hidden ? pause("hidden") : resume("hidden")));
    }

    return { build, pause, resume };
  }

  document.addEventListener("tdm:ready", () => {
    ({ $, el, svg, thumb, fmtDate, loadYT, openPlayer, ICON_PLAY, ICON_INFO, NOCOOKIE, reduceMotion } = TDM);
    trailers = TDM.trailers;
    const hero = makeHero();
    TDM.hero = hero;
    hero.build();
  });
})();
