document.addEventListener("DOMContentLoaded", () => {
  const prefersReduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const saveData = navigator.connection && navigator.connection.saveData;

  const navToggle = document.querySelector("[data-nav-toggle]");
  const siteNav = document.querySelector("[data-site-nav]");
  if (navToggle && siteNav) {
    const label = navToggle.querySelector(".sr-only");
    const setOpen = (open) => {
      siteNav.classList.toggle("is-open", open);
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
      document.body.classList.toggle("nav-open", open);
      if (label) label.textContent = open ? "Close menu" : "Menu";
      if (open) {
        const first = siteNav.querySelector("a");
        if (first) first.focus();
      }
    };
    const header = document.querySelector(".site-header");
    const syncHeaderOffset = () => {
      if (!header) return;
      document.documentElement.style.setProperty("--header-offset", `${header.offsetHeight}px`);
    };
    syncHeaderOffset();
    window.addEventListener("resize", syncHeaderOffset);
    navToggle.addEventListener("click", () => {
      syncHeaderOffset();
      const open = navToggle.getAttribute("aria-expanded") !== "true";
      setOpen(open);
    });
    siteNav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => setOpen(false));
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && navToggle.getAttribute("aria-expanded") === "true") {
        setOpen(false);
        navToggle.focus();
      }
    });
  }

  const yearSelect = document.querySelector("[data-year-select]");
  if (yearSelect) {
    yearSelect.addEventListener("change", () => {
      const value = yearSelect.value;
      const root = (yearSelect.dataset.root || "").replace(/\/$/, "");
      if (value && root) window.location.assign(`${root}/${value}`);
    });
  }

  document.querySelectorAll("[data-sort-form]").forEach((form) => {
    const select = form.querySelector("[data-sort-select]");
    if (!select) return;
    select.addEventListener("change", () => {
      const root = (form.dataset.root || "").replace(/\/$/, "");
      const sort = select.value || "rating";
      if (!root) {
        form.submit();
        return;
      }
      window.location.assign(sort === "rating" ? root : `${root}/sort/${encodeURIComponent(sort)}`);
    });
  });

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

  const activeYear = document.querySelector(".year-chip.is-active");
  if (activeYear && activeYear.scrollIntoView) {
    activeYear.scrollIntoView({ inline: "center", block: "nearest" });
  }

  initHeroSlider(prefersReduced, saveData);
  initEmbedStacks();
  initStaticSearch();
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

function titleFrom(scope, fallback) {
  const heading = scope && scope.querySelector("h1, h2");
  const text = heading && heading.textContent ? heading.textContent.trim() : "";
  return text ? `Trailer: ${text}` : fallback;
}

function initEmbedStacks() {
  const stacks = Array.from(document.querySelectorAll("[data-embed-stack]"));
  if (!stacks.length) return;

  loadYouTubeApi(() => {
    stacks.forEach((stack) => {
      const slots = Array.from(stack.querySelectorAll("[data-embed-slot]"));
      let alive = slots.length;
      const scope = stack.closest("article, section, main") || document;

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
        new window.YT.Player(host.id, {
          videoId: key,
          playerVars: {
            rel: 0,
            modestbranding: 1,
            playsinline: 1,
          },
          events: {
            onReady: (event) => {
              const frame = event.target.getIframe && event.target.getIframe();
              if (frame) frame.title = titleFrom(scope, "Official trailer");
            },
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

function initHeroSlider(prefersReduced, saveData) {
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
  let booting = false;
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
    if (prefersReduced || slides.length < 2 || !player) return;
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
      /* ignore player race */
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
      /* ignore player race */
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

  const bootPlayer = () => {
    if (booting || player || !playerHost || prefersReduced) return;
    booting = true;
    loadYouTubeApi(() => {
      if (!window.YT || !window.YT.Player) return;
      const firstKey = slides[index] && slides[index].dataset.trailerKey;
      if (!firstKey) return;
      if (!playerHost.id) playerHost.id = "hero-yt-player";
      player = new window.YT.Player(playerHost.id, {
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
            const frame = player.getIframe && player.getIframe();
            if (frame) frame.title = "Featured trailer";
            try {
              player.mute();
              player.playVideo();
            } catch (_) {
              /* ignore autoplay block */
            }
            scheduleAdvance();
          },
          onStateChange: (event) => {
            if (!window.YT || !window.YT.PlayerState) return;
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
    });
  };

  if (soundBtn) {
    soundBtn.addEventListener("click", () => {
      soundOn = !soundOn;
      setSoundUi();
      bootPlayer();
      applyMute();
      if (player && typeof player.playVideo === "function") {
        try {
          player.playVideo();
        } catch (_) {
          /* ignore autoplay block */
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

  const wideEnough = window.matchMedia("(min-width: 900px)").matches;
  if (!prefersReduced && !saveData && wideEnough && playerHost) {
    const start = () => bootPlayer();
    if ("requestIdleCallback" in window) window.requestIdleCallback(start, { timeout: 1800 });
    else window.setTimeout(start, 900);
  }

  document.addEventListener("visibilitychange", () => {
    if (!player) return;
    if (document.hidden) {
      clearAdvance();
      try {
        player.pauseVideo();
      } catch (_) {
        /* ignore */
      }
    } else {
      playCurrent();
    }
  });
}

function initStaticSearch() {
  if (document.documentElement.dataset.static !== "true") return;
  const root = document.querySelector("[data-search-root]");
  const indexNode = document.getElementById("search-index");
  if (!root || !indexNode) return;

  let catalog = [];
  try {
    catalog = JSON.parse(indexNode.textContent || "[]");
  } catch (_) {
    catalog = [];
  }

  const params = new URLSearchParams(window.location.search);
  const query = (params.get("q") || "").trim();
  const heading = root.querySelector("[data-search-heading]");
  const summary = root.querySelector("[data-search-summary]");
  const results = root.querySelector("[data-search-results]");
  const empty = root.querySelector("[data-search-empty]");
  const fallback = root.dataset.fallback || "";
  if (!query) return;

  const needle = query.toLowerCase();
  const matches = catalog.filter((item) => String(item.title || "").toLowerCase().includes(needle));
  if (heading) heading.textContent = `Results for “${query}”`;
  if (summary) {
    const noun = matches.length === 1 ? "result" : "results";
    summary.textContent = `${matches.length} trailer-ready ${noun} in the 2daymovie catalog.`;
  }
  if (!results) return;
  results.hidden = matches.length === 0;
  if (empty) empty.hidden = matches.length !== 0;
  results.replaceChildren();

  const play = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  play.setAttribute("viewBox", "0 0 24 24");
  play.setAttribute("width", "22");
  play.setAttribute("height", "22");
  play.setAttribute("fill", "currentColor");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", "M8 5.14v13.72L19 12 8 5.14z");
  play.appendChild(path);

  matches.slice(0, 48).forEach((item) => {
    const link = document.createElement("a");
    link.className = "poster-card";
    link.href = item.href || "#";
    const frame = document.createElement("span");
    frame.className = "poster-frame";
    const img = document.createElement("img");
    img.className = "poster-img";
    img.src = item.poster || fallback;
    img.alt = `Poster for ${item.title || "title"}`;
    img.width = 200;
    img.height = 300;
    img.loading = "lazy";
    img.addEventListener("error", () => {
      img.src = fallback;
    });
    const button = document.createElement("span");
    button.className = "poster-play";
    button.setAttribute("aria-hidden", "true");
    button.appendChild(play.cloneNode(true));
    frame.append(img, button);
    const meta = document.createElement("div");
    meta.className = "poster-meta";
    const title = document.createElement("h3");
    title.textContent = item.title || "Untitled";
    const line = document.createElement("p");
    line.textContent = [item.kind === "Series" ? "Series" : "", item.year || ""].filter(Boolean).join(" · ");
    meta.append(title, line);
    link.append(frame, meta);
    results.appendChild(link);
  });
}
