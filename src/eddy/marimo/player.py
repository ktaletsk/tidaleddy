"""A looping Web Audio player + pianoroll for rendered eddy patterns.

When a new clip arrives while playing, it is swapped in exactly at the next
cycle boundary, so re-running a pattern cell feels like live coding: the
music keeps going and the change lands on the beat.
"""

import anywidget
import traitlets

from eddy.marimo.synth import Render

_ESM = r"""
const DRUM_ORDER = ["bd","sn","sd","cp","rim","lt","mt","ht","hh","oh","cb","cr","perc"];
const PALETTE = ["#e8590c","#1c7ed6","#2f9e44","#ae3ec9","#f08c00","#0ca678","#d6336c","#4263eb","#74b816","#868e96"];

function b64ToBuf(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
}

function lanesFor(events) {
  const pitched = new Map(), drums = new Map();
  for (const e of events) {
    if (e.midi == null) drums.set(e.label, e);
    else pitched.set(e.label, e);
  }
  const p = [...pitched.values()].sort((a, b) => b.midi - a.midi || a.s.localeCompare(b.s)).map(e => e.label);
  const d = [...drums.values()].sort((a, b) => {
    const ia = DRUM_ORDER.indexOf(a.s), ib = DRUM_ORDER.indexOf(b.s);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.label.localeCompare(b.label);
  }).map(e => e.label);
  return [...p, ...d];
}

function render({ model, el }) {
  el.classList.add("vx");
  const bar = document.createElement("div"); bar.className = "vx-bar";
  const play = document.createElement("button"); play.textContent = "▶ Play";
  const stop = document.createElement("button"); stop.textContent = "■ Hush";
  const status = document.createElement("span"); status.className = "vx-status";
  bar.append(play, stop, status);
  const canvas = document.createElement("canvas");
  el.append(bar, canvas);

  let ctx = null, master = null, cur = null, playing = false;
  // timeline: cycle c happens at t0 + c * cycleDur (c grows forever; loop = c mod nCycles)
  let t0 = 0, cycleDur = 2, nCycles = 4;
  let shown = model.get("clip") || {};       // what the pianoroll draws
  let pendingView = null;                    // {clip, at}
  let generation = 0;

  // Other widgets on the page (the path pad) follow the music through this.
  const clock = () => (playing && ctx ? { cycle: (ctx.currentTime - t0) / cycleDur, nCycles, cycleDur } : null);
  globalThis.__eddyClock = clock;

  const colorOf = new Map();
  const color = s => {
    if (!colorOf.has(s)) colorOf.set(s, PALETTE[colorOf.size % PALETTE.length]);
    return colorOf.get(s);
  };

  async function ensureCtx() {
    if (!ctx) {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      master = ctx.createGain(); master.gain.value = 1; master.connect(ctx.destination);
    }
    if (ctx.state === "suspended") await ctx.resume();
  }

  function startSource(buffer, when, offset) {
    const src = ctx.createBufferSource();
    src.buffer = buffer; src.loop = true;
    const g = ctx.createGain(); g.gain.value = 1;
    src.connect(g).connect(master);
    src.start(when, offset % buffer.duration);
    return { src, g };
  }

  function stopSource(node, when) {
    if (!node) return;
    try {
      node.g.gain.setValueAtTime(1, when);
      node.g.gain.linearRampToValueAtTime(0, when + 0.025);
      node.src.stop(when + 0.04);
    } catch (e) {}
  }

  async function swapIn(clip) {
    const my = ++generation;
    if (!clip || !clip.wav) return;
    const buffer = await ctx.decodeAudioData(b64ToBuf(clip.wav));
    if (my !== generation || !playing) return;
    const newDur = 1 / clip.cps, newN = clip.cycles;
    const now = ctx.currentTime;
    let k = Math.ceil((now + 0.06 - t0) / cycleDur);   // next boundary, with decode/latency margin
    const at = t0 + k * cycleDur;
    const node = startSource(buffer, at, (k % newN) * newDur);
    stopSource(cur, at);
    cur = node;
    t0 = at - k * newDur; cycleDur = newDur; nCycles = newN;
    pendingView = { clip, at };
  }

  play.onclick = async () => {
    await ensureCtx();
    const clip = model.get("clip");
    if (!clip || !clip.wav) return;
    if (playing) return;
    playing = true;
    const buffer = await ctx.decodeAudioData(b64ToBuf(clip.wav));
    cycleDur = 1 / clip.cps; nCycles = clip.cycles;
    t0 = ctx.currentTime + 0.05;
    cur = startSource(buffer, t0, 0);
    shown = clip; pendingView = null;
    play.classList.add("on");
  };

  stop.onclick = () => {
    if (!ctx || !playing) return;
    playing = false; generation++;
    stopSource(cur, ctx.currentTime); cur = null;
    play.classList.remove("on");
  };

  // Only one player sounds at a time: starting one stops the others on the page.
  const me = {};
  const onOtherPlay = (e) => { if (e.detail !== me) stop.onclick(); };
  window.addEventListener("eddy:play", onOtherPlay);
  play.addEventListener("click", () => window.dispatchEvent(new CustomEvent("eddy:play", { detail: me })));

  model.on("change:clip", () => {
    const clip = model.get("clip");
    if (playing) swapIn(clip); else { shown = clip; }
  });

  // ---- pianoroll ----
  const dpr = window.devicePixelRatio || 1;
  let W = 600, H = 200;
  function resize() {
    W = Math.max(200, el.clientWidth || 600);
    const lanes = lanesFor(shown.events || []).length;
    H = Math.min(420, Math.max(120, lanes * 16 + 26));
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + "px"; canvas.style.height = H + "px";
  }
  new ResizeObserver(resize).observe(el);

  let raf;
  function draw() {
    raf = requestAnimationFrame(draw);
    if (pendingView && ctx && ctx.currentTime >= pendingView.at) {
      shown = pendingView.clip; pendingView = null; resize();
    }
    const events = shown.events || [];
    const cycles = shown.cycles || 1;
    const lanes = lanesFor(events);
    const want = Math.min(420, Math.max(120, lanes.length * 16 + 26));
    if (Math.abs(want - H) > 1 || Math.abs((el.clientWidth || W) - W) > 1) resize();

    const fg = getComputedStyle(el).color || "#222";
    const g = canvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    const left = 88, top = 4, bottom = 20;
    const plotW = W - left - 6, plotH = H - top - bottom;
    const laneH = lanes.length ? plotH / lanes.length : plotH;
    const x = c => left + (c / cycles) * plotW;

    // playhead position (in loop cycles)
    let pos = null;
    if (playing && ctx) {
      const c = (ctx.currentTime - t0) / cycleDur;
      if (c >= 0) pos = c % nCycles;
      status.textContent = c >= 0 ? `cycle ${Math.floor(c)}  ·  ${(c % 1).toFixed(2)}` : "";
    } else {
      status.textContent = events.length ? `${events.length} events · ${cycles} cycles · press ▶` : "no events";
    }

    // grid
    g.globalAlpha = 1;
    g.font = "11px ui-monospace, SFMono-Regular, Menlo, monospace";
    g.textBaseline = "middle";
    for (let i = 0; i < lanes.length; i++) {
      if (i % 2 === 0) {
        g.fillStyle = fg; g.globalAlpha = 0.04;
        g.fillRect(left, top + i * laneH, plotW, laneH);
      }
      g.globalAlpha = 0.75; g.fillStyle = fg;
      const lbl = lanes[i].length > 13 ? lanes[i].slice(0, 12) + "…" : lanes[i];
      g.fillText(lbl, 4, top + (i + 0.5) * laneH);
    }
    for (let c = 0; c <= cycles * 4; c++) {
      g.globalAlpha = c % 4 === 0 ? 0.35 : 0.1;
      g.fillStyle = fg;
      g.fillRect(Math.round(x(c / 4)), top, 1, plotH);
    }
    g.globalAlpha = 0.6;
    for (let c = 0; c < cycles; c++) g.fillText(String(c), x(c) + 3, H - 9);

    // events
    const laneIdx = new Map(lanes.map((l, i) => [l, i]));
    for (const e of events) {
      const i = laneIdx.get(e.label);
      const active = pos != null && pos >= e.begin && pos < e.end;
      g.globalAlpha = active ? 1 : 0.35 + 0.45 * Math.min(1, e.gain);
      g.fillStyle = active ? fg : color(e.s);
      const x0 = x(e.begin) + 1, w = Math.max(2, x(e.end) - x(e.begin) - 2);
      g.fillRect(x0, top + i * laneH + 1.5, w, Math.max(2, laneH - 3));
    }

    // playhead
    if (pos != null) {
      g.globalAlpha = 0.9; g.fillStyle = "#e03131";
      g.fillRect(x(pos), top, 2, plotH);
    }
    g.globalAlpha = 1;
  }
  resize(); draw();
  window.dispatchEvent(new CustomEvent("eddy:ready"));  // lets a page know Python is up

  return () => {
    cancelAnimationFrame(raf);
    window.removeEventListener("eddy:play", onOtherPlay);
    playing = false;
    if (globalThis.__eddyClock === clock) delete globalThis.__eddyClock;
    if (cur && ctx) stopSource(cur, ctx.currentTime);
    if (ctx) ctx.close();
  };
}

export default { render };
"""

_CSS = """
.vx { font-family: system-ui, sans-serif; width: 100%; color: var(--eddy-fg, var(--foreground, currentColor)); }
/* Text colour. A page can set --eddy-fg (custom properties cross shadow roots and follow theme
   switches). Otherwise use marimo's theme: --foreground, or light text under its .dark wrapper,
   whose dark colours don't reach inside a shadow root (as in marimo islands). */
.dark .vx { color: var(--eddy-fg, #e6ebf1); }
.vx-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.vx-bar button {
  font: inherit; font-size: 13px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  border: 1px solid color-mix(in srgb, currentColor 30%, transparent);
  background: color-mix(in srgb, currentColor 6%, transparent); color: inherit;
}
.vx-bar button.on { background: #2f9e44; color: white; border-color: #2f9e44; }
.vx-status { font-family: ui-monospace, Menlo, monospace; font-size: 12px; opacity: .7; margin-left: 6px; }
.vx canvas { display: block; border-radius: 6px;
  background: color-mix(in srgb, currentColor 3%, transparent); }
"""


class Player(anywidget.AnyWidget):
    _esm = _ESM
    _css = _CSS
    clip = traitlets.Dict({}).tag(sync=True)

    def load(self, r: Render) -> None:
        self.clip = clip_of(r)


def clip_of(r: Render) -> dict:
    """The `clip` trait value for a render."""
    return {"wav": r.wav_b64, "events": r.events, "cycles": r.cycles, "cps": r.cps}


def play(pattern, cycles: int = 2, cps: float = 0.5) -> Player:
    """A player loaded with `pattern`: the quickest way to hear a pattern in a cell.

        play(s("bd hh sn hh"))
    """
    from .synth import render

    player = Player()
    player.load(render(pattern, cycles, cps))
    return player
