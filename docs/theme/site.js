// eddy docs: theme switch, mobile nav, copy buttons, "On this page" highlighting,
// and the Python status shown while the islands start.
(function () {
  "use strict";
  var root = document.documentElement;

  // ---- light / dark ----
  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var dark = !root.classList.contains("dark");
      root.classList.toggle("dark", dark);
      root.classList.toggle("dark-theme", dark);
      try { localStorage.setItem("eddy-theme", dark ? "dark" : "light"); } catch (e) {}
    });
  }

  // ---- mobile nav ----
  var navToggle = document.querySelector(".nav-toggle");
  if (navToggle) {
    navToggle.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
  }

  // ---- copy buttons on static code blocks ----
  document.querySelectorAll(".prose .highlight").forEach(function (block) {
    if (block.closest(".eddy-fallback")) return;
    var pre = block.querySelector("pre");
    if (!pre) return;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "copy-button";
    button.textContent = "Copy";
    button.addEventListener("click", function () {
      navigator.clipboard.writeText(pre.innerText.replace(/\n$/, "")).then(function () {
        button.textContent = "Copied";
        setTimeout(function () { button.textContent = "Copy"; }, 1400);
      }, function () {});
    });
    block.appendChild(button);
  });

  // ---- "On this page": highlight the section being read ----
  var links = Array.prototype.slice.call(document.querySelectorAll(".toc a"));
  var targets = links.map(function (a) { return document.getElementById(decodeURIComponent(a.hash.slice(1))); });
  if (links.length && "IntersectionObserver" in window) {
    var visible = new Map();
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { visible.set(e.target, e.isIntersecting); });
      var first = targets.findIndex(function (t) { return t && visible.get(t); });
      if (first >= 0) links.forEach(function (a, i) { a.classList.toggle("active", i === first); });
    }, { rootMargin: "-64px 0px -60% 0px" });
    targets.forEach(function (t) { if (t) io.observe(t); });
  }

  // ---- islands: tell the reader when Python is ready ----
  if (document.body.dataset.islands !== "true") return;
  var status = document.querySelector(".py-status");
  var statusText = status && status.querySelector(".py-text");
  var started = Date.now();
  function setStatus(state, text) {
    if (!status) return;
    status.hidden = false;
    status.dataset.state = state;
    statusText.textContent = text;
  }
  setStatus("loading", "Starting Python…");

  // widgets render inside shadow roots, so look through them
  function deepFind(node, selector) {
    if (node.querySelector) {
      var hit = node.querySelector(selector);
      if (hit) return hit;
    }
    var all = node.querySelectorAll ? node.querySelectorAll("*") : [];
    for (var i = 0; i < all.length; i++) {
      if (all[i].shadowRoot) {
        var found = deepFind(all[i].shadowRoot, selector);
        if (found) return found;
      }
    }
    return null;
  }

  var blocks = Array.prototype.slice.call(document.querySelectorAll(".eddy-repl-block"));
  var timer = setInterval(function () {
    var ready = 0;
    blocks.forEach(function (block) {
      if (block.classList.contains("is-live")) { ready++; return; }
      var island = block.querySelector("marimo-island");
      if (island && deepFind(island, ".eddy-repl")) { block.classList.add("is-live"); ready++; }
    });
    var error = deepFind(document.body, "marimo-island .marimo-error, marimo-island [data-testid='marimo-error']");
    if (error) {
      setStatus("error", "Python hit an error");
    } else if (blocks.length && ready === blocks.length) {
      setStatus("ready", "Python ready · " + ((Date.now() - started) / 1000).toFixed(0) + "s");
      clearInterval(timer);
      setTimeout(function () { status.classList.add("fade"); }, 6000);
    } else if (!blocks.length && window.__eddyPlayerSeen) {
      setStatus("ready", "Python ready");
      clearInterval(timer);
    } else if (Date.now() - started > 8000) {
      setStatus("loading", "Starting Python… (the first visit downloads ~25 MB)");
    }
  }, 400);
  window.addEventListener("eddy:ready", function () { window.__eddyPlayerSeen = true; });
})();
