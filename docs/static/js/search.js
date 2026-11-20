/* 2DayMovie search: instant, accent-insensitive title search across the
   catalog and the upcoming trailers. Results open in the shared grid view. */
(() => {
  "use strict";
  const TDM = (window.TDM = window.TDM || {});
  let $, norm, showResults, hideResults;

  function search(q) {
    const terms = norm(q).split(/\s+/).filter(Boolean);
    if (!terms.length) return hideResults();
    const pool = [...TDM.trailers.map((t) => ({ ...t, title: t.film })), ...TDM.catalog.videos];
    const hits = pool.filter((v) => {
      const hay = norm(`${v.title} ${v.row || ""} ${v.film ? "trailer upcoming" : ""}`);
      return terms.every((t) => hay.includes(t));
    });
    showResults(`Results for “${q.trim()}”`, hits);
  }

  function bind() {
    const input = $("#searchInput");
    let t = 0;
    input.addEventListener("input", () => {
      clearTimeout(t);
      t = setTimeout(() => (input.value.trim().length >= 2 ? search(input.value) : hideResults()), 160);
    });
    $("#searchForm").addEventListener("submit", (e) => { e.preventDefault(); if (input.value.trim()) search(input.value); input.blur(); });
  }

  document.addEventListener("tdm:ready", () => {
    ({ $, norm, showResults, hideResults } = TDM);
    bind();
  });
})();
