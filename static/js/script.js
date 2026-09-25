document.addEventListener("DOMContentLoaded", () => {
  const prefersReduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const navToggle = document.querySelector("[data-nav-toggle]");
  const siteNav = document.querySelector("[data-site-nav]");
  if (navToggle && siteNav) {
    navToggle.addEventListener("click", () => {
      const open = siteNav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
      document.body.classList.toggle("nav-open", open);
    });
  }

  const yearSelect = document.querySelector("[data-year-select]");
  if (yearSelect) {
    yearSelect.addEventListener("change", () => {
      const url = yearSelect.value;
      if (url) window.location.assign(url);
    });
  }

  // Year accordion: only one panel open; navigate to load that year's shelf
  const accordion = document.querySelector("[data-year-accordion]");
  if (accordion) {
    accordion.querySelectorAll("details.year-panel").forEach((panel) => {
      panel.addEventListener("toggle", () => {
        if (!panel.open) return;
        accordion.querySelectorAll("details.year-panel").forEach((other) => {
          if (other !== panel) other.open = false;
        });
        const link = panel.querySelector(".year-panel-hint a");
        if (link && !panel.querySelector(".shelf-grid")) {
          window.location.assign(link.href);
        }
      });
    });
  }

  initHeroSlider(prefersReduced);
  initEmbedStacks();

  const revealables = document.querySelectorAll(
    ".row, .home-block, .poster-card, .detail-layout, .library-card, .year-row, .category-tile"
  );

  if (prefersReduced) {
    revealables.forEach((el) => el.classList.add("is-visible"));
    return;
  }

  const staggerGroups = new WeakMap();
  const nextStaggerIndex = (el) => {
    const parent = el.parentElement;
    if (!parent) return 0;
    const current = staggerGroups.get(parent) || 0;
    staggerGroups.set(parent, current + 1);
    return current;
  };

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const el = entry.target;
          if (el.matches(".poster-card, .library-card, .year-row, .category-tile")) {
            const i = nextStaggerIndex(el);
            el.style.transitionDelay = `${Math.min(i, 12) * 35}ms`;
          }
          el.classList.add("is-visible");
          observer.unobserve(el);
        });
      },
      { threshold: 0.06, rootMargin: "0px 0px -2% 0px" }
    );
    revealables.forEach((el) => observer.observe(el));
  } else {
    revealables.forEach((el) => el.classList.add("is-visible"));
  }
});

function loadYouTubeApi(callback) {
  if (window.YT && window.YT.Player) {
    callback();
    return;
  }
  const previous = window.onYouTubeIframeAPIReady;
  window.onYouTubeIframeAPIReady = () => {
    if (typeof previous === "function") previous();
    callback();
  };
  if (!document.getElementById("yt-iframe-api")) {
    const tag = document.createElement("script");
    tag.id = "yt-iframe-api";
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
  }
}

function initEmbedStacks() {
  const stacks = Array.from(document.querySelectorAll("[data-embed-stack]"));
  if (!stacks.length) return;

  loadYouTubeApi(() => {
    stacks.forEach((stack) => {
      const slots = Array.from(stack.querySelectorAll("[data-embed-slot]"));
      let alive = slots.length;

      const maybeEmpty = () => {
        if (alive > 0) return;
        const note = document.createElement("p");
        note.className = "watch-note";
        note.textContent =
          "No on-site trailer is available for this title (embedding disabled by the owner).";
        stack.replaceChildren(note);
      };

      slots.forEach((slot, i) => {
        const key = slot.getAttribute("data-yt-key");
        const host = slot.querySelector(".watch-yt-host") || slot;
        if (!key) {
          slot.classList.add("is-rejected");
          alive -= 1;
          maybeEmpty();
          return;
        }
        if (!host.id) host.id = `embed-yt-${Date.now()}-${i}`;
        // eslint-disable-next-line no-new
        new window.YT.Player(host.id, {
          videoId: key,
          playerVars: {
            rel: 0,
            modestbranding: 1,
            playsinline: 1,
            origin: window.location.origin,
          },
          events: {
            onError: (event) => {
              const code = event && event.data;
              if (code === 101 || code === 150 || code === 100 || code === 2) {
                slot.classList.add("is-rejected");
                const label = slot.nextElementSibling;
                if (label && label.hasAttribute("data-embed-label")) {
                  label.hidden = true;
                }
                alive -= 1;
                maybeEmpty();
              }
            },
          },
        });
      });
    });
  });
}

function initHeroSlider(prefersReduced) {
  const root = document.querySelector("[data-hero-slider]");
  if (!root) return;

  const slides = Array.from(root.querySelectorAll(".hero-slide"));
  if (!slides.length) return;

  const soundBtn = root.querySelector("[data-hero-sound]");
  const titleLink = root.querySelector("[data-hero-title]");
  const dots = Array.from(root.querySelectorAll("[data-hero-dot]"));
  let index = 0;
  let soundOn = false;
  let players = [];
  let advanceTimer = null;
  const SLIDE_MS = 28000;

  const setSoundUi = () => {
    if (!soundBtn) return;
    soundBtn.setAttribute("aria-pressed", soundOn ? "true" : "false");
    soundBtn.textContent = soundOn ? "Sound on" : "Turn sound on";
  };

  const updateMeta = (slide) => {
    if (!titleLink || !slide) return;
    const title = slide.dataset.title || "Trailer";
    const year = slide.dataset.year || "";
    titleLink.textContent = year ? `${title} · ${year}` : title;
    titleLink.href = slide.dataset.href || "#";
  };

  const clearAdvance = () => {
    if (advanceTimer) {
      window.clearTimeout(advanceTimer);
      advanceTimer = null;
    }
  };

  const scheduleAdvance = () => {
    clearAdvance();
    if (prefersReduced || slides.length < 2) return;
    advanceTimer = window.setTimeout(() => goTo((index + 1) % slides.length), SLIDE_MS);
  };

  const applyMute = () => {
    players.forEach((p, i) => {
      if (!p || typeof p.mute !== "function") return;
      if (soundOn && i === index) {
        p.unMute();
        p.setVolume(100);
      } else {
        p.mute();
      }
    });
  };

  const playActive = () => {
    players.forEach((p, i) => {
      if (!p || typeof p.pauseVideo !== "function") return;
      if (i === index) {
        try {
          p.seekTo(0, true);
          if (soundOn) {
            p.unMute();
            p.setVolume(100);
          } else {
            p.mute();
          }
          p.playVideo();
        } catch (_) {
          /* ignore */
        }
      } else {
        try {
          p.pauseVideo();
          p.mute();
        } catch (_) {
          /* ignore */
        }
      }
    });
  };

  const goTo = (next) => {
    if (next === index && players[next]) {
      playActive();
      scheduleAdvance();
      return;
    }
    index = next;
    slides.forEach((slide, i) => slide.classList.toggle("is-active", i === index));
    dots.forEach((dot, i) => {
      const on = i === index;
      dot.classList.toggle("is-active", on);
      if (on) dot.setAttribute("aria-current", "true");
      else dot.removeAttribute("aria-current");
    });
    updateMeta(slides[index]);
    playActive();
    scheduleAdvance();
  };

  if (soundBtn) {
    soundBtn.addEventListener("click", () => {
      soundOn = !soundOn;
      setSoundUi();
      applyMute();
      const active = players[index];
      if (active && typeof active.playVideo === "function") {
        try {
          active.playVideo();
        } catch (_) {
          /* ignore */
        }
      }
    });
  }

  dots.forEach((dot) => {
    dot.addEventListener("click", () => {
      const i = Number(dot.getAttribute("data-hero-dot"));
      if (!Number.isNaN(i)) goTo(i);
    });
  });

  updateMeta(slides[0]);
  setSoundUi();

  if (prefersReduced) {
    // Still-image wallpaper only — no autoplay video.
    return;
  }

  const bootPlayers = () => {
    players = slides.map((slide, i) => {
      const mount = slide.querySelector("[data-yt-mount]");
      const key = slide.dataset.trailerKey;
      if (!mount || !key || !window.YT || !window.YT.Player) return null;
      const host = document.createElement("div");
      host.id = `hero-yt-${i}`;
      mount.appendChild(host);
      return new window.YT.Player(host.id, {
        videoId: key,
        playerVars: {
          autoplay: i === 0 ? 1 : 0,
          mute: 1,
          controls: 0,
          rel: 0,
          modestbranding: 1,
          playsinline: 1,
          fs: 0,
          disablekb: 1,
          iv_load_policy: 3,
          origin: window.location.origin,
        },
        events: {
          onReady: (event) => {
            event.target.mute();
            soundOn = false;
            setSoundUi();
            if (i === index) {
              event.target.playVideo();
              scheduleAdvance();
            } else {
              event.target.pauseVideo();
            }
          },
          onStateChange: (event) => {
            if (i !== index) return;
            if (event.data === window.YT.PlayerState.ENDED) {
              goTo((index + 1) % slides.length);
            }
            if (event.data === window.YT.PlayerState.PLAYING) {
              applyMute();
            }
          },
          onError: (event) => {
            // 101 / 150 = embedding disabled by owner — skip this slide.
            const code = event && event.data;
            if ((code === 101 || code === 150 || code === 100 || code === 2) && slides.length > 1) {
              if (i === index) goTo((index + 1) % slides.length);
            }
          },
        },
      });
    });
  };

  loadYouTubeApi(bootPlayers);
}
