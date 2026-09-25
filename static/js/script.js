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
