document.addEventListener("DOMContentLoaded", () => {
  const prefersReduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const yearSelect = document.querySelector("[data-year-select]");
  if (yearSelect) {
    yearSelect.addEventListener("change", () => {
      const url = yearSelect.value;
      if (url) window.location.assign(url);
    });
  }

  const revealables = document.querySelectorAll(
    ".row, .poster-card, .detail-layout, .library-card, .year-row"
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
          if (el.matches(".poster-card, .library-card, .year-row")) {
            const i = nextStaggerIndex(el);
            el.style.transitionDelay = `${Math.min(i, 12) * 40}ms`;
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
