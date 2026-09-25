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
  const fallback = root.querySelector("[data-hero-fallback]");
  const playerHost = root.querySelector("[data-hero-player]");
  const dots = Array.from(root.querySelectorAll("[data-hero-dot]"));
  let index = 0;
  let soundOn = false;
  let player = null;
  let advanceTimer = null;
  let ready = false;
  const SLIDE_MS = 28000;

  const setSoundUi = () => {
    if (!soundBtn) return;
    soundBtn.setAttribute("aria-pressed", soundOn ? "true" : "false");
    soundBtn.textContent = soundOn ? "Sound on" : "Turn sound on";
  };

  const syncFallback = (slide) => {
    if (!fallback || !slide) return;
    const backdrop = slide.dataset.backdrop;
    if (backdrop) fallback.style.setProperty("--hero-image", `url('${backdrop}')`);
  };

  const updateMeta = (slide) => {
    if (!titleLink || !slide) return;
    const title = slide.dataset.title || "Trailer";
    const year = slide.dataset.year || "";
    titleLink.textContent = year ? `${title} · ${year}` : title;
    titleLink.href = slide.dataset.href || "#";
    syncFallback(slide);
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
    if (!player || typeof player.mute !== "function") return;
    try {
      if (soundOn) {
        player.unMute();
        player.setVolume(100);
      } else {
        player.mute();
      }
    } catch (_) {
      /* ignore */
    }
  };

  const playCurrent = () => {
    if (!player || !ready) return;
    const key = slides[index] && slides[index].dataset.trailerKey;
    if (!key) return;
    try {
      const current = typeof player.getVideoData === "function" ? player.getVideoData() : null;
      const same = current && current.video_id === key;
      if (same) {
        applyMute();
        player.playVideo();
      } else if (typeof player.loadVideoById === "function") {
        player.mute();
        player.loadVideoById({ videoId: key, startSeconds: 0 });
        window.setTimeout(applyMute, 300);
      }
    } catch (_) {
      /* ignore */
    }
    scheduleAdvance();
  };

  const goTo = (next) => {
    index = ((next % slides.length) + slides.length) % slides.length;
    slides.forEach((slide, i) => slide.classList.toggle("is-active", i === index));
    dots.forEach((dot, i) => {
      const on = i === index;
      dot.classList.toggle("is-active", on);
      if (on) dot.setAttribute("aria-current", "true");
      else dot.removeAttribute("aria-current");
    });
    updateMeta(slides[index]);
    playCurrent();
  };

  if (soundBtn) {
    soundBtn.addEventListener("click", () => {
      soundOn = !soundOn;
      setSoundUi();
      applyMute();
      if (player && typeof player.playVideo === "function") {
        try {
          player.playVideo();
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

  if (prefersReduced || !playerHost) {
    return;
  }

  const bootPlayer = () => {
    if (!window.YT || !window.YT.Player) return;
    const firstKey = slides[0].dataset.trailerKey;
    if (!firstKey) return;

    if (!playerHost.id) playerHost.id = "hero-yt-player";
    playerHost.innerHTML = "";

    player = new window.YT.Player(playerHost.id, {
      width: "100%",
      height: "100%",
      videoId: firstKey,
      playerVars: {
        autoplay: 1,
        mute: 1,
        controls: 0,
        rel: 0,
        modestbranding: 1,
        playsinline: 1,
        fs: 0,
        disablekb: 1,
        iv_load_policy: 3,
      },
      events: {
        onReady: (event) => {
          ready = true;
          player = event.target;
          try {
            player.mute();
            player.playVideo();
          } catch (_) {
            /* ignore */
          }
          scheduleAdvance();
        },
        onStateChange: (event) => {
          if (event.data === window.YT.PlayerState.PLAYING) {
            applyMute();
            root.classList.add("is-playing");
          }
          if (event.data === window.YT.PlayerState.ENDED && slides.length > 1) {
            goTo((index + 1) % slides.length);
          }
        },
        onError: (event) => {
          const code = event && event.data;
          if ((code === 101 || code === 150 || code === 100 || code === 2) && slides.length > 1) {
            goTo((index + 1) % slides.length);
          }
        },
      },
    });
  };

  loadYouTubeApi(bootPlayer);
}
