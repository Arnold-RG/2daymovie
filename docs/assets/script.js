document.addEventListener("DOMContentLoaded", () => {
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

  const revealables = document.querySelectorAll(".row, .poster-card, .detail-layout");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    revealables.forEach((el) => observer.observe(el));
  }
});
