/* 2DayMovie search: instant, accent-insensitive title search across the
   catalog and the upcoming trailers. Results open in the shared grid view. */
(() => {
  "use strict";
  const TDM = (window.TDM = window.TDM || {});
  let $, showResults, hideResults;

  const MAX_QUERY = 100;
  const fold = (s) => String(s).normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

  // Pure, DOM-free matcher (unit-tested from tests/test_search.py through node):
  // only ever returns objects taken from the catalog videos and trailers passed in.
  function searchItems(q, videos, trailers) {
    const terms = fold(String(q || "").slice(0, MAX_QUERY)).split(/\s+/).filter(Boolean);
    if (!terms.length) return [];
    const pool = [...(trailers || []).map((t) => ({ ...t, title: t.film })), ...(videos || [])];
    return pool.filter((v) => {
      const genres = Array.isArray(v.genres) ? v.genres.join(" ") : "";
      const hay = fold(`${v.title} ${v.row || ""} ${genres} ${v.film ? "trailer upcoming" : ""}`);
      return terms.every((t) => hay.includes(t));
    });
  }
  TDM.searchItems = searchItems;

  function search(q) {
    const hits = searchItems(q, TDM.catalog.videos, TDM.trailers);
    if (!String(q).trim()) return hideResults();
    // showResults renders with textContent only, so the query is never parsed as HTML
    showResults(`Results for “${String(q).trim().slice(0, MAX_QUERY)}”`, hits);
  }

  function bind() {
    const input = $("#searchInput");
    input.maxLength = MAX_QUERY;
    let t = 0;
    input.addEventListener("input", () => {
      clearTimeout(t);
      t = setTimeout(() => (input.value.trim().length >= 2 ? search(input.value) : hideResults()), 160);
    });
    $("#searchForm").addEventListener("submit", (e) => { e.preventDefault(); if (input.value.trim()) search(input.value); input.blur(); });
  }

  document.addEventListener("tdm:ready", () => {
    ({ $, showResults, hideResults } = TDM);
    bind();
  });
})();
