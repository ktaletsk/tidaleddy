"""Hear and play with eddy patterns in a marimo notebook.

Needs the `marimo` extra: `pip install "tidaleddy[marimo]"`.

    import marimo as mo
    from eddy import s, n, stack, scale
    from eddy.marimo import Player, Repl, TangleStack, PathPad, play, render

    Repl('s("bd hh sn hh")')                    # the quickest start: edit, drag, press ▶
    play(stack(s("bd*2"), n("0 3 7").s("pluck")))   # hear any pattern built in Python

    player = Player()
    mo.ui.anywidget(player)                     # ▶ Play / ■ Hush and a pianoroll

    editor = mo.ui.anywidget(TangleStack('s("bd*4")', 's("hh*8").gain(0.6)'))
    editor                                      # type code; drag numbers, click sound names

    # in another cell
    player.load(render(editor.widget.pattern(), cycles=4, cps=0.5))

Everything here is synthesized with numpy, in the notebook's Python process.
No SuperCollider is needed.
"""

from .path_pad import PathPad, PathSignals
from .player import Player, play
from .repl import Repl
from .synth import SOUND_NAMES, Render, flatten_value, query_events, render
from .tangle_stack import TangleStack

__all__ = [
    "PathPad",
    "PathSignals",
    "Player",
    "Render",
    "Repl",
    "SOUND_NAMES",
    "TangleStack",
    "flatten_value",
    "play",
    "query_events",
    "render",
]
