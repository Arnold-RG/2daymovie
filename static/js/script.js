document.addEventListener("DOMContentLoaded", () => {
  const prefersReduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const rails = document.querySelectorAll("[data-rail]");
  rails.forEach((rail) => {
    rail.addEventListener(
      "wheel",
      (event) => {
        if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
        event.preventDefault();
        rail.scrollLeft += event.deltaY;
      },
      { passive: false }
    );
  });

  // Keep active year pill in view on the sticky switcher
  const switcher = document.querySelector("[data-year-switcher]");
  if (switcher) {
    const active = switcher.querySelector(".year-pill.is-active");
    if (active && typeof active.scrollIntoView === "function") {
      active.scrollIntoView({
        inline: "center",
        block: "nearest",
        behavior: prefersReduced ? "auto" : "smooth",
      });
    }
  }

  const revealables = document.querySelectorAll(
    ".row, .poster-card, .detail-layout, .library-card, .year-card"
  );

  if (prefersReduced) {
    revealables.forEach((el) => el.classList.add("is-visible"));
    return;
  }

  // Stagger poster / year shelf reveals within a common parent
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
          if (el.matches(".poster-card, .library-card, .year-card")) {
            const i = nextStaggerIndex(el);
            el.style.transitionDelay = `${Math.min(i, 12) * 45}ms`;
          }
          el.classList.add("is-visible");
          observer.unobserve(el);
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -3% 0px" }
    );
    revealables.forEach((el) => observer.observe(el));
  } else {
    revealables.forEach((el) => el.classList.add("is-visible"));
  }
});
