"""A small live-coding box: type a pattern, drag its numbers, press ▶.

    Repl('s("bd hh sn hh")')                  # one line: just the code
    Repl('s("bd*2 sn")', 'n("0 3 7").s("pluck")', cycles=4)   # several lines: a stack(...)

`Repl` is the `TangleStack` editor and the `Player` in one widget. Every edit is
evaluated and rendered in Python straight away, and if it's playing, the new
sound comes in on the next cycle. It needs nothing else in the notebook, which
makes it handy for docs and tutorials (it is what the eddy docs use).
"""

from __future__ import annotations

import json

import traitlets

from .player import _CSS as _PLAYER_CSS
from .player import _ESM as _PLAYER_ESM
from .player import clip_of
from .synth import render
from .tangle_stack import _CSS as _STACK_CSS
from .tangle_stack import _ESM as _STACK_ESM
from .tangle_stack import _WIGGLY_SRC, TangleStack


def _scoped(esm: str, name: str) -> str:
    """Wrap a widget's front-end module in a function, so two can share one module."""
    tail = "export default { render };"
    assert esm.rstrip().endswith(tail), name
    body = esm.rstrip()[: -len(tail)]
    return f"const {name} = (() => {{\n{body}\nreturn {{ render }};\n}})();\n"


_ESM = (
    f"const WIGGLY = {json.dumps(_WIGGLY_SRC)};\n"
    + _scoped(_STACK_ESM, "STACK")
    + _scoped(_PLAYER_ESM, "PLAYER")
    + r"""
async function render({ model, el }) {
  el.classList.add("eddy-repl");
  const sync = () => el.classList.toggle("eddy-compact", !!model.get("compact"));
  sync();
  model.on("change:compact", sync);
  const code = document.createElement("div"); code.className = "eddy-repl-code";
  const sound = document.createElement("div"); sound.className = "eddy-repl-sound";
  el.append(code, sound);
  const cleanups = [await STACK.render({ model, el: code }), PLAYER.render({ model, el: sound })];
  window.dispatchEvent(new CustomEvent("eddy:ready"));
  return () => cleanups.forEach((f) => { try { f && f(); } catch (e) {} });
}

export default { render };
"""
)

_CSS = _STACK_CSS + _PLAYER_CSS + """
.eddy-repl { display: flex; flex-direction: column; gap: 6px; color: var(--eddy-fg, var(--foreground, currentColor)); }
.dark .eddy-repl { color: var(--eddy-fg, #e6ebf1); }
.eddy-repl .ts { padding: 8px 12px; }
.eddy-compact .ts-edge, .eddy-compact .ts-add, .eddy-compact .ts-ind, .eddy-compact .ts-mute,
.eddy-compact .ts-bar, .eddy-compact .ts-hint, .eddy-compact .ts-comma { display: none !important; }
.eddy-compact .ts-line { padding-left: 0; }
.eddy-repl .ts-hint { font-size: 11.5px; }
"""


class Repl(TangleStack):
    """Code you can edit and play: the stack editor and a player in one widget."""

    _esm = _ESM
    _css = _CSS

    clip = traitlets.Dict({}).tag(sync=True)
    compact = traitlets.Bool(False).tag(sync=True)
    cycles = traitlets.Int(2).tag(sync=True)
    cps = traitlets.Float(0.5).tag(sync=True)

    def __init__(self, *lines: str, cycles: int = 2, cps: float = 0.5, compact: bool | None = None, **kwargs):
        """`lines` are layers of code, as for TangleStack. One line shows as plain code."""
        super().__init__(*lines, **kwargs)
        self.cycles, self.cps = cycles, cps
        self.compact = (len(self.layers) == 1) if compact is None else compact
        self.observe(lambda _: self.update(), names=["layers", "cycles", "cps"])
        self.update()

    def update(self) -> None:
        """Evaluate the code and render it again."""
        self.clip = clip_of(render(self.pattern(), self.cycles, self.cps))
