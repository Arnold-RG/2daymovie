/**
 * Arnova shared client helpers — XSS-safe DOM + IndexedDB vault + reveal motion.
 * No secrets. Safe for public static sites.
 */
(function (global) {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function text(el, value) {
    if (!el) return;
    el.textContent = value == null ? "" : String(value);
  }

  function hardenExternalLinks(root) {
    var scope = root || document;
    scope.querySelectorAll('a[href^="http"]').forEach(function (a) {
      try {
        var url = new URL(a.href, location.href);
        if (url.origin !== location.origin) {
          a.setAttribute("rel", "noopener noreferrer");
          if (!a.target) a.target = "_blank";
        }
      } catch (e) { /* ignore bad URLs */ }
    });
  }

  function initReveals(root) {
    var scope = root || document;
    var nodes = scope.querySelectorAll(".arn-reveal");
    if (!nodes.length) return;
    if (!("IntersectionObserver" in window)) {
      nodes.forEach(function (n) { n.classList.add("is-in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    nodes.forEach(function (n) { io.observe(n); });
  }

  function openDb(name, version, onUpgrade) {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(name, version || 1);
      req.onupgradeneeded = function (ev) {
        if (typeof onUpgrade === "function") onUpgrade(ev.target.result, ev);
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function idbPut(db, store, value, key) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(store, "readwrite");
      var os = tx.objectStore(store);
      var req = key === undefined ? os.put(value) : os.put(value, key);
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function idbGet(db, store, key) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(store, "readonly");
      var req = tx.objectStore(store).get(key);
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function idbGetAll(db, store) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(store, "readonly");
      var req = tx.objectStore(store).getAll();
      req.onsuccess = function () { resolve(req.result || []); };
      req.onerror = function () { reject(req.error); };
    });
  }

  async function sha256Hex(str) {
    var data = new TextEncoder().encode(String(str));
    var buf = await crypto.subtle.digest("SHA-256", data);
    return Array.from(new Uint8Array(buf)).map(function (b) {
      return b.toString(16).padStart(2, "0");
    }).join("");
  }

  function boot() {
    hardenExternalLinks(document);
    initReveals(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  global.ArnovaSecure = {
    escapeHtml: escapeHtml,
    text: text,
    hardenExternalLinks: hardenExternalLinks,
    initReveals: initReveals,
    openDb: openDb,
    idbPut: idbPut,
    idbGet: idbGet,
    idbGetAll: idbGetAll,
    sha256Hex: sha256Hex
  };
})(typeof window !== "undefined" ? window : globalThis);
