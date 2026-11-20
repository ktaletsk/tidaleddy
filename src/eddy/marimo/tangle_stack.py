"""A Tangle-style `stack(...)` code editor for eddy patterns, built on wigglystuff's Tangle widgets.

Each layer is one line of plain eddy code that you can type into. Inside it,
numbers and sound names automatically become inline Tangle controls:

  * numbers      -> drag left/right, or click to type a value  (wigglystuff TangleSlider)
  * sound names  -> click to cycle, inside s("...")            (wigglystuff TangleChoice)
  * scale names  -> click to cycle, inside scale("...", ...)   (wigglystuff TangleChoice)
  * 🔊 / 🔇      -> mute a layer                               (wigglystuff TangleChoice)

Click anywhere else on a line to edit it as text (Enter commits, Esc cancels,
↑/↓ move between lines, an empty line is removed), add a line with
"+ add a layer", or use "✎ edit as text" to edit or paste the whole stack.

The editor is ONE anywidget: it runs wigglystuff's own Tangle front-end modules
for each control against a small shim model, and syncs plain lines of code.

    editor = mo.ui.anywidget(TangleStack(
        's("bd*4").gain(1.0)',
        '# s("hh*8")',               # a leading "#" starts the layer muted
    ))
    editor

    # another cell (referencing `editor` makes it re-run on every change)
    pat = editor.widget.pattern()
"""

from __future__ import annotations

import json
from pathlib import Path

import anywidget
import traitlets
import eddy
import wigglystuff

from eddy.scales import SCALE_NAMES

# Everything eddy exports (scale() included), for evaluating layer code.
NAMESPACE = {k: getattr(eddy, k) for k in dir(eddy) if not k.startswith("_")}

_STATIC = Path(wigglystuff.__file__).parent / "static"
_WIGGLY_SRC = {
    "slider": (_STATIC / "tangle-slider.js").read_text(),
    "choice": (_STATIC / "tangle-choice.js").read_text(),
}

_ESM = r"""
const ON = "🔊", OFF = "🔇";
const NUM_RE = /(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])/g;
const STR_RE = /"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g;
const WORD_RE = /[A-Za-z_]\w*/g;

const mods = {};
async function load(kind) {
  if (!mods[kind]) {
    const url = URL.createObjectURL(new Blob([WIGGLY[kind]], { type: "text/javascript" }));
    try { mods[kind] = (await import(url)).default; } finally { URL.revokeObjectURL(url); }
  }
  return mods[kind];
}

// Split one line of code into plain text and tangle-able tokens.
function tokenize(code, sounds) {
  const strings = [...code.matchAll(STR_RE)].map((m) => [m.index, m.index + m[0].length]);
  const inString = (i) => strings.some(([a, b]) => i > a && i < b - 1);
  const toks = [];
  for (const m of code.matchAll(NUM_RE)) {
    toks.push({ start: m.index, end: m.index + m[0].length, kind: "num", inStr: inString(m.index) });
  }
  for (const [a, b] of strings) {
    const before = code.slice(0, a), body = code.slice(a + 1, b - 1);
    if (/(?:^|[^\w])(?:s|sound)\(\s*$/.test(before)) {            // sound names inside s("...")
      for (const w of body.matchAll(WORD_RE)) {
        const group = sounds.drums.includes(w[0]) ? sounds.drums : sounds.synths.includes(w[0]) ? sounds.synths : null;
        if (group) toks.push({ start: a + 1 + w.index, end: a + 1 + w.index + w[0].length, kind: "sound", group });
      }
    } else if (/(?:^|[^\w])scale\(\s*$/.test(before) && (sounds.scales || []).includes(body)) {
      toks.push({ start: a + 1, end: b - 1, kind: "sound", group: sounds.scales });   // scale("minor", ...)
    }
  }
  toks.sort((x, y) => x.start - y.start);
  const parts = [];
  let pos = 0;
  for (const t of toks) {
    if (t.start < pos) continue;
    if (t.start > pos) parts.push({ text: code.slice(pos, t.start), start: pos });
    parts.push({ ...t, text: code.slice(t.start, t.end) });
    pos = t.end;
  }
  if (pos < code.length) parts.push({ text: code.slice(pos), start: pos });
  return parts;
}

function sliderState(text, inStr) {
  const v = parseFloat(text);
  const digits = (text.split(".")[1] || "").length;
  const step = digits ? Math.pow(10, -digits)
    : Math.abs(v) >= 100 ? Math.pow(10, Math.floor(Math.log10(Math.abs(v))) - 1) : 1;
  return {   // the same traits as wigglystuff.TangleSlider
    amount: v, committed_amount: v, dragging: false,
    min_value: inStr || v < 0 ? -1e6 : 0, max_value: 1e6, step, steps: [],
    pixels_per_step: digits === 1 ? 8 : digits ? 3 : step === 1 ? 6 : 3, prefix: "", suffix: "", digits,
  };
}

const fmt = (x, digits) => { const s = Number(x).toFixed(digits); return /^-0(\.0*)?$/.test(s) ? s.slice(1) : s; };

async function render({ model, el }) {
  el.classList.add("ts-wrap");
  const bar = document.createElement("div"); bar.className = "ts-bar";
  const toggle = document.createElement("button"); toggle.textContent = "✎ edit as text";
  bar.appendChild(toggle);
  const root = document.createElement("div"); root.className = "ts";
  const hint = document.createElement("div"); hint.className = "ts-hint";
  el.append(bar, root, hint);

  let layers = structuredClone(model.get("layers"));
  let parts = [];          // per line: tokenized parts
  let ctl = {};            // control key -> shim state
  let cleanups = [];
  let lineEls = [];
  let editing = null;      // {i, input, done}
  let textMode = null;     // textarea while editing everything as text
  let syncTimer = null;

  const SAY_TANGLE = "click code to type · drag <u>numbers</u> ↔ (shift ×10, alt ×0.1, click to type a value) · " +
    "click <u>sound</u> and <u>scale</u> names to cycle · 🔊 mutes a layer";
  const SAY_LINE = "typing · <b>↵</b> apply · <b>esc</b> cancel · <b>↑ ↓</b> other lines · empty line = delete";
  const SAY_TEXT = "one layer per line, <code>#</code> mutes it · <b>⌘/ctrl + ↵</b> or <b>✓ done</b> to apply · <b>esc</b> cancels";
  hint.innerHTML = SAY_TANGLE;

  const stop = (e) => e.stopPropagation();   // keep marimo's shortcuts out of our inputs
  const guardKeys = (node) => ["keydown", "keyup", "keypress"].forEach((t) => node.addEventListener(t, stop));

  const anyDragging = () => Object.values(ctl).some((s) => s.dragging);
  function sync() {
    if (syncTimer) return;
    syncTimer = setTimeout(() => {
      syncTimer = null;
      model.set("layers", structuredClone(layers));
      model.set("dragging", anyDragging());
      model.save_changes();
    }, 0);
  }

  function shim(key, onSet) {
    return {
      get: (name) => ctl[key]?.[name],
      set: (name, val) => {
        const s = ctl[key];
        s[name] = val;
        if (name === "amount" && !s.dragging) s.committed_amount = val;
        onSet && onSet(name, val);
      },
      save_changes: () => { decorate(); sync(); },
      on: () => {}, off: () => {}, send: () => {},
    };
  }

  function decorate() {
    const errors = model.get("errors") || {};
    layers.forEach((L, i) => {
      const row = lineEls[i];
      if (!row) return;
      row.classList.toggle("ts-off", !L.on);
      const err = L.on ? errors[String(i)] : null;
      row.classList.toggle("ts-err", !!err);
      const w = row.querySelector(".ts-warn");
      if (w) w.title = err || "";
    });
  }

  const span = (t, cls = "ts-code") => { const s = document.createElement("span"); s.className = cls; s.textContent = t; return s; };

  async function mount(kind, key, holder, onSet) {
    const mod = await load(kind);
    cleanups.push(await mod.render({ model: shim(key, onSet), el: holder }));
  }

  function caretAt(e, i) {
    const rn = el.getRootNode();
    let node = null, off = 0;
    try {
      if (document.caretPositionFromPoint) {
        const p = document.caretPositionFromPoint(e.clientX, e.clientY, rn instanceof ShadowRoot ? { shadowRoots: [rn] } : undefined);
        if (p) { node = p.offsetNode; off = p.offset; }
      } else if (document.caretRangeFromPoint) {
        const r = document.caretRangeFromPoint(e.clientX, e.clientY);
        if (r) { node = r.startContainer; off = r.startOffset; }
      }
    } catch (err) {}
    const host = node && (node.nodeType === 3 ? node.parentElement : node);
    if (host && host.dataset && host.dataset.start !== undefined && lineEls[i]?.contains(host)) {
      return Number(host.dataset.start) + off;
    }
    return layers[i].code.length;
  }

  function buildLine(i) {
    const L = layers[i];
    const row = document.createElement("div");
    row.className = "ts-line";
    row.appendChild(span("", "ts-ind"));
    const mute = document.createElement("span"); mute.className = "ts-ctl ts-mute";
    row.appendChild(mute);
    const jobs = [];
    const mk = `${i}:on`;
    ctl[mk] = { choices: [ON, OFF], choice: L.on ? ON : OFF };
    jobs.push(mount("choice", mk, mute, (name, v) => { if (name === "choice") layers[i].on = v === ON; }));

    const ps = tokenize(L.code, model.get("sounds"));
    parts[i] = ps;
    ps.forEach((p, j) => {
      if (!p.kind) {
        const s = span(p.text); s.dataset.start = p.start; row.appendChild(s);
        return;
      }
      const holder = document.createElement("span"); holder.className = "ts-ctl";
      row.appendChild(holder);
      const key = `${i}:${j}`;
      const rewrite = (text) => { p.text = text; layers[i].code = ps.map((q) => q.text).join(""); };
      if (p.kind === "num") {
        ctl[key] = sliderState(p.text, p.inStr);
        jobs.push(mount("slider", key, holder, (name, v) => { if (name === "amount") rewrite(fmt(v, ctl[key].digits)); }));
      } else {
        ctl[key] = { choices: p.group, choice: p.text };
        jobs.push(mount("choice", key, holder, (name, v) => { if (name === "choice") rewrite(v); }));
      }
    });
    if (!L.code) row.appendChild(span("…", "ts-code ts-empty"));
    row.appendChild(span(",", "ts-code ts-comma"));
    row.appendChild(span("⚠", "ts-warn"));

    row.addEventListener("click", (e) => {
      // composedPath, not target.closest: TangleChoice re-renders on click, so the
      // clicked node is already detached from the row by the time the event gets here.
      const onCtl = e.composedPath().some((n) => n.classList && n.classList.contains("ts-ctl"));
      if (onCtl || editing || textMode) return;
      editLine(i, caretAt(e, i));
    });
    return { row, jobs };
  }

  async function build() {
    cleanups.forEach((f) => { try { f && f(); } catch (e) {} });
    cleanups = []; ctl = {}; parts = []; lineEls = []; editing = null;
    root.innerHTML = "";
    const edge = (t) => { const d = document.createElement("div"); d.className = "ts-line ts-edge"; d.appendChild(span(t)); return d; };
    root.appendChild(edge("stack("));
    const jobs = [];
    layers.forEach((_, i) => {
      const { row, jobs: j } = buildLine(i);
      root.appendChild(row); lineEls.push(row); jobs.push(...j);
    });
    const add = document.createElement("div"); add.className = "ts-line ts-add";
    add.appendChild(span("", "ts-ind")); add.appendChild(span("", "ts-mute"));
    add.appendChild(span("+ add a layer", "ts-code"));
    add.addEventListener("click", () => {
      if (editing || textMode) return;
      layers.push({ code: "", on: true });
      build().then(() => editLine(layers.length - 1, 0));
    });
    root.appendChild(add);
    root.appendChild(edge(")"));
    await Promise.all(jobs);
    decorate();
  }

  function editLine(i, caret) {
    if (i < 0 || i >= layers.length) return;
    const row = lineEls[i];
    const input = document.createElement("input");
    input.className = "ts-input";
    input.value = layers[i].code;
    input.spellcheck = false;
    input.placeholder = 's("bd*4").gain(0.8)';
    guardKeys(input);
    // replace the code part of the row (keep indent + mute)
    [...row.children].slice(2).forEach((c) => c.remove());
    row.appendChild(input);
    row.classList.add("ts-editing");
    hint.innerHTML = SAY_LINE;
    editing = { i, input, done: false };
    input.focus();
    input.setSelectionRange(caret, caret);

    const finish = (apply, move = 0) => {
      if (!editing || editing.done) return;
      editing.done = true;
      const col = input.selectionStart;
      const text = input.value.trim().replace(/,\s*$/, "");
      let target = i + move;
      if (apply) {
        if (text) layers[i].code = text;
        else { layers.splice(i, 1); if (move > 0) target -= 1; }
      } else if (!layers[i].code) {
        layers.splice(i, 1);
      }
      hint.innerHTML = SAY_TANGLE;
      editing = null;
      sync();
      build().then(() => { if (move) editLine(target, Math.min(col, layers[target]?.code.length ?? 0)); });
    };
    input.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a") { e.preventDefault(); input.select(); }
      else if (e.key === "Enter") { e.preventDefault(); finish(true); }
      else if (e.key === "Escape") { e.preventDefault(); finish(false); }
      else if (e.key === "ArrowUp" && i > 0) { e.preventDefault(); finish(true, -1); }
      else if (e.key === "ArrowDown" && i < layers.length - 1) { e.preventDefault(); finish(true, +1); }
    });
    input.addEventListener("blur", () => finish(true));
  }

  // ---- whole stack as text ----
  function enterTextMode() {
    if (editing) editing.input.blur();
    const ta = document.createElement("textarea");
    ta.className = "ts-textarea";
    ta.spellcheck = false;
    ta.value = layers.map((L) => (L.on ? "" : "# ") + L.code).join("\n");
    ta.rows = Math.max(4, layers.length + 1);
    guardKeys(ta);
    root.innerHTML = "";
    root.appendChild(ta);
    textMode = ta;
    toggle.textContent = "✓ done";
    hint.innerHTML = SAY_TEXT;
    ta.focus();
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); leaveTextMode(true); }
      else if (e.key === "Escape") { e.preventDefault(); leaveTextMode(false); }
    });
  }
  function leaveTextMode(apply) {
    if (!textMode) return;
    if (apply) {
      layers = textMode.value.split("\n")
        .map((l) => l.trim().replace(/,\s*$/, ""))
        .filter((l) => l && l !== "#" && !/^(stack\(|\)|pat\s*=\s*stack\()\s*$/.test(l))
        .map((l) => (l.startsWith("#") ? { code: l.replace(/^#\s*/, ""), on: false } : { code: l, on: true }));
      sync();
    }
    textMode = null;
    toggle.textContent = "✎ edit as text";
    hint.innerHTML = SAY_TANGLE;
    build();
  }
  toggle.addEventListener("click", () => (textMode ? leaveTextMode(true) : enterTextMode()));

  // Python -> JS
  model.on("change:layers", () => {
    const incoming = model.get("layers");
    if (JSON.stringify(incoming) === JSON.stringify(layers) || editing || textMode) return;
    layers = structuredClone(incoming);
    build();
  });
  model.on("change:errors", decorate);

  await build();
  return () => cleanups.forEach((f) => { try { f && f(); } catch (e) {} });
}

export default { render };
"""

_CSS = """
.ts-wrap { position: relative; color: var(--eddy-fg, var(--foreground, currentColor)); }  /* see .vx in player.py */
.dark .ts-wrap { color: var(--eddy-fg, #e6ebf1); }
.ts { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13.5px;
      line-height: 2.1; padding: 10px 14px; border-radius: 8px; overflow-x: auto;
      background: color-mix(in srgb, currentColor 4%, transparent); }
/* long lines wrap with a hanging indent; the first two items pull back into the padding */
.ts-line { display: flex; flex-wrap: wrap; align-items: baseline; padding-left: 7.2ch; cursor: text;
           border-radius: 4px; }
.ts-line:not(.ts-edge):not(.ts-editing):hover { background: color-mix(in srgb, currentColor 5%, transparent); }
.ts-line.ts-edge { padding-left: 0; cursor: default; }
.ts-line > * { flex: none; }
.ts-code { white-space: pre; opacity: .8; }
.ts-ind { display: inline-block; width: 2ch; margin-left: -7.2ch; }
.ts-mute { display: inline-block; width: 3.2ch; cursor: pointer; }
.ts-mute .tangle-value { text-decoration: none !important; }
.ts .tangle-value, .ts input:not(.ts-input) { color: #2b7de9 !important; font: inherit !important; }
.ts .tangle-value { text-decoration-thickness: 1px !important; text-underline-offset: 3px; }
.ts-empty { opacity: .35; }
.ts-add { opacity: .45; }
.ts-add:hover { opacity: .85; }
.ts-add .ts-code { font-style: italic; }
.ts-input { flex: 1 1 auto !important; min-width: 20ch; font: inherit; color: inherit;
            background: color-mix(in srgb, currentColor 7%, transparent);
            border: 1px solid color-mix(in srgb, #2b7de9 60%, transparent); border-radius: 4px;
            padding: 0 4px; margin: 0 0 0 -5px; outline: none; line-height: 1.7; }
.ts-textarea { width: 100%; box-sizing: border-box; font: inherit; line-height: 1.7; color: inherit;
               background: transparent; border: 1px solid color-mix(in srgb, #2b7de9 60%, transparent);
               border-radius: 6px; padding: 6px 8px; outline: none; resize: vertical; white-space: pre;
               overflow-x: auto; }
.ts-off > :not(.ts-mute):not(.ts-ind) { opacity: .35; }
.ts-warn { display: none; color: #e03131; margin-left: 1ch; cursor: help; }
.ts-err .ts-warn { display: inline; }
.ts-err .ts-code { color: #e03131; }
.ts-bar { position: absolute; top: 6px; right: 8px; z-index: 1; }
.ts-bar button { font: 12px system-ui, sans-serif; padding: 2px 8px; border-radius: 5px; cursor: pointer;
                 color: inherit; background: color-mix(in srgb, currentColor 6%, transparent);
                 border: 1px solid color-mix(in srgb, currentColor 25%, transparent); }
.ts-hint { font-family: system-ui, sans-serif; font-size: 12px; opacity: .6; margin-top: 4px; }
.ts-hint code { font-size: 11px; }
"""


class TangleStack(anywidget.AnyWidget):
    """A `stack(...)` of eddy layers you can type into, with Tangle controls inline."""

    _esm = f"const WIGGLY = {json.dumps(_WIGGLY_SRC)};\n" + _ESM
    _css = _CSS

    layers = traitlets.List([]).tag(sync=True)      # [{"code": str, "on": bool}]
    sounds = traitlets.Dict({}).tag(sync=True)      # {"drums": [...], "synths": [...], "scales": [...]}
    errors = traitlets.Dict({}).tag(sync=True)      # {"<line index>": message}
    dragging = traitlets.Bool(False).tag(sync=True)

    def __init__(self, *lines: str, sounds: dict | None = None, namespace: dict | None = None, **kwargs):
        if sounds is None:
            from eddy.marimo.synth import SOUND_NAMES as sounds
        self.namespace = {**NAMESPACE, **(namespace or {})}
        layers = []
        for line in lines:
            t = line.strip()
            on = not t.startswith("#")
            layers.append({"code": t.lstrip("#").strip().rstrip(",").rstrip(), "on": on})
        super().__init__(
            layers=layers,
            sounds={"drums": list(sounds["drums"]), "synths": list(sounds["synths"]), "scales": SCALE_NAMES},
            **kwargs,
        )

    def code(self) -> str:
        """The current stack as plain eddy code (muted layers commented out)."""
        body = "\n".join(f"    {L['code']}," if L["on"] else f"    # {L['code']},"
                         for L in self.layers if L["code"])
        return "stack(\n" + body + "\n)"

    def pattern(self, **names):
        """Evaluate the active layers into one eddy pattern.

        Keyword arguments become extra names the layers can use, e.g.
        `pattern(path=path)` lets a layer say `.pan(path.x)`.

        A layer that fails to evaluate is skipped and flagged red in the
        editor (hover the ⚠ for the message).
        """
        scope = {**self.namespace, **names}
        pats, errors = [], {}
        for i, L in enumerate(self.layers):
            src = L["code"].strip().rstrip(",")
            if not L["on"] or not src:
                continue
            try:
                p = eval(src, dict(scope))
                if not isinstance(p, eddy.Pattern):
                    raise TypeError(f"this line is a {type(p).__name__}, not a Pattern")
                p.query(eddy.TimeSpan(0, 1))  # surface mini-notation errors now
                pats.append(p)
            except Exception as ex:  # noqa: BLE001 - shown to the user
                errors[str(i)] = f"{type(ex).__name__}: {str(ex).splitlines()[0][:200] if str(ex) else ''}"
        if errors != self.errors:
            self.errors = errors
        return eddy.stack(*pats) if pats else eddy.silence()
