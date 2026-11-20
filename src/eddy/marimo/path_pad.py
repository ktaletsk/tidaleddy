"""A path you shape by hand, whose moving dot drives eddy patterns.

The pad is wigglystuff's CurveEditor: drag knots to shape a closed loop,
double-click to add or remove a knot, pick how the curve is drawn. Instead of
CurveEditor's own play button, the dot is driven by the audio clock of the
`Player` widget, so it shows exactly where the music is: one lap per loop
(or 2, 3, ... laps, set under the pad).

In Python the same path becomes eddy patterns:

    pad = mo.ui.anywidget(PathPad(seed=7))
    pad

    # another cell (referencing `pad` re-runs it whenever the shape changes)
    path = pad.widget.path(cycles=4)        # the loop is 4 cycles long
    path.x, path.y                          # signals in 0..1, like sine()
    path.knots                              # a hit each time the dot passes a knot

    n(scale("minpent", path.y.range(0, 10).segment(8))).s("pluck").pan(path.x)
    s("rim").struct(path.knots)

Like `TangleStack`, this is ONE anywidget that runs wigglystuff's own front-end
modules (CurveEditor, TangleSlider) against small shim models.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import anywidget
import numpy as np
import traitlets
import eddy
import wigglystuff

_STATIC = Path(wigglystuff.__file__).parent / "static"
_WIGGLY_SRC = {
    "curve": (_STATIC / "curve-editor.js").read_text(),
    "slider": (_STATIC / "tangle-slider.js").read_text(),
}
N_SAMPLES = 129      # points along one lap, evenly spaced by distance; first == last
HIT_STEPS = 16       # path.knots snaps to this many steps per cycle


def blob(seed=None, knots: int = 6) -> list[dict]:
    """A random closed shape: `knots` points scattered around the centre of the pad."""
    rng = random.Random(seed)
    start = rng.random() * math.tau
    pts = []
    for k in range(knots):
        angle = start + math.tau * (k + rng.uniform(-0.25, 0.25)) / knots
        radius = rng.uniform(0.16, 0.46)
        pts.append({"x": round(0.5 + radius * math.cos(angle), 3),
                    "y": round(0.5 + radius * math.sin(angle), 3)})
    return pts


def _lap_signal(values: np.ndarray, period: float):
    """A eddy signal that reads `values` (one closed lap) once every `period` cycles."""
    n = len(values) - 1

    def at(t):
        u = (float(t) / period) % 1.0 * n
        i = min(int(u), n - 1)
        f = u - i
        return float(values[i] * (1 - f) + values[i + 1] * f)

    return eddy.signal(at)


class PathSignals:
    """What a path gives to patterns. Made by `PathPad.path(cycles)`."""

    def __init__(self, xs, ys, knot_laps, cycles: int, laps: int):
        self.cycles, self.laps = max(1, int(cycles)), max(1, int(laps))
        period = self.cycles / self.laps
        #: the dot's left-to-right position, a signal in 0..1
        self.x = _lap_signal(np.asarray(xs, dtype=float), period)
        #: the dot's height, a signal in 0..1 (1 = top of the pad)
        self.y = _lap_signal(np.asarray(ys, dtype=float), period)
        #: a hit each time the dot passes a knot, snapped to 16ths. Use with .struct()
        self.knots = self._hits(knot_laps)

    def _hits(self, knot_laps):
        total = self.cycles * HIT_STEPS
        slots = sorted({round((lap + u) / self.laps * total) % total
                        for lap in range(self.laps) for u in knot_laps})
        parts, pos = [], 0
        for s in slots:
            if s > pos:
                parts.append((s - pos, eddy.silence()))
            parts.append((1, eddy.pure(True)))
            pos = s + 1
        if not parts:
            return eddy.silence()
        if pos < total:
            parts.append((total - pos, eddy.silence()))
        return eddy.timecat(*parts).slow(self.cycles)

    def __repr__(self):
        return f"<path: {self.laps} lap(s) per {self.cycles}-cycle loop. Use path.x, path.y, path.knots>"


_ESM = r"""
const mods = {};
async function load(kind) {
  if (!mods[kind]) {
    const url = URL.createObjectURL(new Blob([WIGGLY[kind]], { type: "text/javascript" }));
    try { mods[kind] = (await import(url)).default; } finally { URL.revokeObjectURL(url); }
  }
  return mods[kind];
}

const clamp01 = (v) => Math.max(0, Math.min(1, Number(v) || 0));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function randomBlob(n) {
  const start = Math.random() * 2 * Math.PI, pts = [];
  for (let k = 0; k < n; k++) {
    const a = start + 2 * Math.PI * (k + (Math.random() - 0.5) * 0.5) / n;
    const r = 0.16 + Math.random() * 0.30;
    pts.push({ x: +(0.5 + r * Math.cos(a)).toFixed(3), y: +(0.5 + r * Math.sin(a)).toFixed(3) });
  }
  return pts;
}

async function render({ model, el }) {
  el.classList.add("pp");
  const pad = document.createElement("div"); pad.className = "pp-pad";
  const cap = document.createElement("div"); cap.className = "pp-cap";
  el.append(pad, cap);

  // ---- the CurveEditor, running against a shim model ----
  const st = {   // the same traits as wigglystuff.CurveEditor
    points: structuredClone(model.get("points")), samples: [], x: 0, y: 0, t: 0,
    show_axes: false, n_samples: N_SAMPLES,
    curve: model.get("curve"), tension: model.get("tension"), alpha: model.get("alpha"),
    closed: true, playing: false, loop: true, interval_ms: 30, duration_ms: 12000,
    sync_throttle_ms: 0, selected_index: -1, x_bounds: [0, 1], y_bounds: [0, 1],
    width: model.get("width"), height: model.get("height"),
  };
  const SYNCED = new Set(["points", "samples", "curve", "tension", "alpha"]);
  const listeners = {};
  const emit = (name) => (listeners[name] || []).forEach((f) => { try { f(); } catch (e) { console.error(e); } });

  let dirty = false, dragging = false, syncTimer = null;
  let knotAt = [];   // for each knot: how far along the lap it sits, 0..1

  function sync() {
    if (syncTimer) return;
    syncTimer = setTimeout(() => {
      syncTimer = null; dirty = false;
      model.set("points", structuredClone(st.points));
      model.set("samples", structuredClone(st.samples));
      model.set("curve", st.curve);
      model.set("tension", st.tension);
      model.set("alpha", st.alpha);
      model.set("dragging", dragging);
      model.save_changes();
    }, 50);
  }

  function findKnots() {
    const s = st.samples, n = s.length - 1;
    return st.points.map((p) => {
      let best = 0, bestD = Infinity;
      for (let i = 0; i < n; i++) {
        const d = (s[i].x - p.x) ** 2 + (s[i].y - p.y) ** 2;
        if (d < bestD) { bestD = d; best = i; }
      }
      return n > 0 ? best / n : 0;
    });
  }

  const curveModel = {
    get: (k) => st[k],
    set: (k, v) => {
      if (k === "closed" || k === "loop" || k === "playing") return;   // fixed: the audio clock drives the dot
      if (k === "points") v = v.map((p) => ({ x: clamp01(p.x), y: clamp01(p.y) }));
      if (SYNCED.has(k) && !same(st[k], v)) dirty = true;
      st[k] = v;
      if (k === "samples") knotAt = findKnots();
    },
    save_changes: () => { if (dirty) sync(); },
    on: (name, f) => { (listeners[name] ||= []).push(f); },
    off: () => {}, send: () => {},
  };

  const curve = await load("curve");
  const cleanupCurve = await curve.render({ model: curveModel, el: pad });

  const svg = pad.querySelector("svg");
  // CurveEditor sets height="auto" on every redraw, which is not a valid SVG
  // attribute and logs a console error each time. The CSS aspect-ratio already sizes it.
  const setAttribute = svg.setAttribute.bind(svg);
  svg.setAttribute = (name, value) => { if (!(name === "height" && value === "auto")) setAttribute(name, value); };

  // axis labels over the drawing area, named as they are used in code
  const stage = document.createElement("div"); stage.className = "pp-stage";
  svg.replaceWith(stage);
  const axis = (cls, text) => { const d = document.createElement("div"); d.className = "pp-axis " + cls; d.textContent = text; return d; };
  stage.append(svg, axis("pp-x", "path.x →"), axis("pp-y", "↑ path.y"));

  // The pad always shows 0..1: no wheel-zoom (it would hijack page scrolling) and no panning.
  pad.addEventListener("wheel", (e) => e.stopPropagation(), { capture: true, passive: true });
  pad.addEventListener("pointerdown", (e) => {
    if (e.target.classList && e.target.classList.contains("curve-editor-point")) dragging = true;
    else if (svg.contains(e.target)) e.stopPropagation();
  }, true);
  const release = () => { if (dragging) { dragging = false; sync(); } };
  window.addEventListener("pointerup", release, true);
  window.addEventListener("pointercancel", release, true);

  // ---- caption: new shape, laps ----
  const dice = document.createElement("button"); dice.className = "pp-dice"; dice.textContent = "🎲 new shape";
  dice.title = "A random loop with the same number of knots";
  dice.addEventListener("click", () => {
    st.points = randomBlob(st.points.length); st.selected_index = -1; dirty = true;
    emit("change:points");
  });
  const text = (t) => { const s = document.createElement("span"); s.textContent = t; return s; };
  const lapsHolder = document.createElement("span"); lapsHolder.className = "pp-laps";
  const hint = document.createElement("div"); hint.className = "pp-hint";
  hint.textContent = "drag a knot · double-click to add one · double-click a knot to remove it";
  const row = document.createElement("div"); row.className = "pp-row";
  row.append(dice, text("the dot laps the path"), lapsHolder, text("per loop"));
  cap.append(row, hint);

  const laps = {   // the same traits as wigglystuff.TangleSlider
    amount: model.get("laps"), committed_amount: model.get("laps"), dragging: false,
    min_value: 1, max_value: 8, step: 1, steps: [], pixels_per_step: 14, prefix: "", suffix: "×", digits: 0,
  };
  const lapsListeners = [];
  const slider = await load("slider");
  const cleanupLaps = await slider.render({
    el: lapsHolder,
    model: {
      get: (k) => laps[k],
      set: (k, v) => { laps[k] = v; if (k === "amount" && !laps.dragging) laps.committed_amount = v; },
      save_changes: () => {
        const v = Math.round(laps.amount);
        if (v !== model.get("laps")) { model.set("laps", v); model.save_changes(); }
      },
      on: (name, f) => { if (name === "change:amount") lapsListeners.push(f); },
      off: () => {}, send: () => {},
    },
  });
  // laps set from Python (pad.widget.laps = 3) shows up in the control too
  model.on("change:laps", () => {
    const v = model.get("laps");
    if (v === laps.amount || laps.dragging) return;
    laps.amount = laps.committed_amount = v;
    lapsListeners.forEach((f) => f());
  });

  // ---- Python -> JS ----
  for (const k of ["points", "curve", "tension", "alpha"]) {
    model.on("change:" + k, () => {
      const incoming = model.get(k);
      if (same(incoming, st[k])) return;
      st[k] = structuredClone(incoming);
      emit("change:" + k);
    });
  }

  // ---- theme: CurveEditor only knows dark mode from a class on an ancestor ----
  const applyTheme = () => {
    const m = getComputedStyle(el).color.match(/[\d.]+/g);
    pad.classList.toggle("dark-theme", !!m && 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2] > 140);
  };
  applyTheme();
  const themeTimer = setInterval(applyTheme, 1500);

  // ---- the dot follows the audio clock that the Player widget publishes ----
  // Moving CurveEditor's own dot and trace directly is much lighter than asking it
  // to re-render (which rebuilds the grid and every knot) 60 times a second.
  const pathEl = svg.querySelector(".curve-editor-path");
  const traceEl = svg.querySelector(".curve-editor-trace");
  const dotEl = svg.querySelector(".curve-editor-current");
  let raf = 0;
  function frame() {
    raf = requestAnimationFrame(frame);
    const clock = typeof globalThis.__eddyClock === "function" ? globalThis.__eddyClock() : null;
    if (!clock || !(clock.cycle >= 0)) return;
    const nLaps = Math.max(1, model.get("laps") || 1);
    const t = (((clock.cycle % clock.nCycles) / clock.nCycles) * nLaps) % 1;
    st.t = t;   // so CurveEditor draws the dot in the right place when it does re-render
    let total = 0;
    try { total = pathEl.getTotalLength(); } catch (e) {}
    if (!(total > 0)) return;
    const p = pathEl.getPointAtLength(total * t);
    dotEl.setAttribute("cx", p.x);
    dotEl.setAttribute("cy", p.y);
    traceEl.setAttribute("stroke-dasharray", `${total * t} ${Math.max(0, total - total * t)}`);
    // knots light up as the dot passes them
    const lapSeconds = (clock.nCycles * clock.cycleDur) / nLaps;
    const glow = Math.min(0.2, 0.25 / lapSeconds);   // about a quarter of a second, in laps
    svg.querySelectorAll(".curve-editor-point").forEach((c, i) => {
      const since = knotAt[i] === undefined ? 1 : (((t - knotAt[i]) % 1) + 1) % 1;
      if (since < glow) {
        c.setAttribute("r", 6 + 6 * (1 - since / glow));
        c.classList.add("pp-hit");
      } else if (c.classList.contains("pp-hit")) {
        c.setAttribute("r", 6);
        c.classList.remove("pp-hit");
      }
    });
  }
  frame();

  return () => {
    cancelAnimationFrame(raf);
    clearInterval(themeTimer);
    window.removeEventListener("pointerup", release, true);
    window.removeEventListener("pointercancel", release, true);
    for (const f of [cleanupCurve, cleanupLaps]) { try { f && f(); } catch (e) {} }
  };
}

export default { render };
"""

_CSS = """
.pp { display: inline-block; font-family: system-ui, sans-serif; color: var(--eddy-fg, var(--foreground, currentColor)); }
.dark .pp { color: var(--eddy-fg, #e6ebf1); }
.pp .curve-editor-wrapper { --curve-editor-curve: #2b7de9; --curve-editor-trace: #e8590c;
                            --curve-editor-accent: #e8590c; max-width: 100%; }
.pp .curve-editor-timeline { display: none; }      /* the audio clock drives the dot instead */
.pp .curve-editor-controls { flex-wrap: wrap; row-gap: 4px; }
.pp .curve-editor-svg { cursor: default; }
.pp .curve-editor-current { r: 7px; }
.pp .curve-editor-point.pp-hit { fill: #e8590c; stroke: #e8590c; }
.pp-stage { position: relative; }
.pp-axis { position: absolute; pointer-events: none; opacity: .5;
           font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; }
.pp-x { right: 10px; bottom: 8px; }
.pp-y { left: 10px; top: 8px; }
.pp-cap { margin-top: 6px; font-size: 12.5px; }
.pp-row { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; }
.pp-row > span:not(.pp-laps) { opacity: .75; }
.pp-laps .tangle-value { color: #2b7de9 !important; font-weight: 600; }
.pp-dice { font: inherit; padding: 2px 8px; margin-right: 4px; border-radius: 5px; cursor: pointer; color: inherit;
           background: color-mix(in srgb, currentColor 6%, transparent);
           border: 1px solid color-mix(in srgb, currentColor 25%, transparent); }
.pp-hint { opacity: .55; font-size: 12px; margin-top: 3px; }
"""


class PathPad(anywidget.AnyWidget):
    """A closed path with a dot that travels along it in time with the music."""

    _esm = f"const WIGGLY = {json.dumps(_WIGGLY_SRC)};\nconst N_SAMPLES = {N_SAMPLES};\n" + _ESM
    _css = (_STATIC / "curve-editor.css").read_text() + _CSS

    points = traitlets.List([]).tag(sync=True)       # the knots, in order: [{"x": 0..1, "y": 0..1}]
    samples = traitlets.List([]).tag(sync=True)      # the drawn curve, measured by the browser
    curve = traitlets.Unicode("catmull_rom").tag(sync=True)   # any CurveEditor curve name
    tension = traitlets.Float(0.0).tag(sync=True)
    alpha = traitlets.Float(0.5).tag(sync=True)
    laps = traitlets.Int(1).tag(sync=True)           # laps of the path per loop
    dragging = traitlets.Bool(False).tag(sync=True)
    width = traitlets.Int(380).tag(sync=True)
    height = traitlets.Int(300).tag(sync=True)

    def __init__(self, points: list[dict] | None = None, *, seed=None, knots: int = 6, **kwargs):
        """Start from `points`, or from a random shape with `knots` knots made from `seed`."""
        if points is None:
            points = blob(seed, knots)
        super().__init__(points=[{"x": float(p["x"]), "y": float(p["y"])} for p in points], **kwargs)

    def _lap(self) -> tuple[np.ndarray, np.ndarray]:
        """x and y along one lap, evenly spaced by distance, ending where it starts."""
        if len(self.samples) >= 3:
            xs = np.array([p["x"] for p in self.samples], dtype=float)
            ys = np.array([p["y"] for p in self.samples], dtype=float)
        else:
            # The browser hasn't measured the curve yet (or there is no browser):
            # use straight lines between the knots.
            pts = self.points + self.points[:1]
            px = np.array([p["x"] for p in pts], dtype=float)
            py = np.array([p["y"] for p in pts], dtype=float)
            along = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(px), np.diff(py)))])
            if along[-1] <= 0:
                return np.full(N_SAMPLES, px[0]), np.full(N_SAMPLES, py[0])
            at = np.linspace(0.0, along[-1], N_SAMPLES)
            xs, ys = np.interp(at, along, px), np.interp(at, along, py)
        xs[-1], ys[-1] = xs[0], ys[0]
        return np.clip(xs, 0, 1), np.clip(ys, 0, 1)

    def path(self, cycles: int = 1) -> PathSignals:
        """The path as eddy patterns, for a loop that is `cycles` cycles long."""
        xs, ys = self._lap()
        n = len(xs) - 1
        knot_laps = [
            int(np.argmin((xs[:n] - p["x"]) ** 2 + (ys[:n] - p["y"]) ** 2)) / n
            for p in self.points
        ]
        return PathSignals(xs, ys, knot_laps, cycles, self.laps)
