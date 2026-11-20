# Based on vortex/__init__.py from Vortex (https://codeberg.org/uzu/vortex),
# commit aefea84ddde0b5f5e8e94c5a15d00504cb5e2439.
# Copyright (C) the Vortex authors ("Tidal Cyclists"). Licensed under GPL-3.0-or-later.
# Modified for tidaleddy, 2026-11-20: reads its version from the `tidaleddy`
# distribution; removed `vortex_dsl()` and the `vortex.vortex` module, which need
# the live-coding clock, OSC streaming and GUI that tidaleddy leaves out; added `scale`.
"""eddy: the TidalCycles pattern engine from Vortex, without the GUI or OSC.

    from eddy import n, s, stack, sine, scale

    pat = stack(
        s("bd(3,8) sn"),
        n(scale("minor", "0 2 4 <6 7>")).s("superpiano"),
    )
    pat.query(TimeSpan(0, 1))          # the events in the first cycle

To hear patterns in a marimo notebook, install `tidaleddy[marimo]` and see
`eddy.marimo`.
"""

from importlib import metadata

try:
    __version__ = metadata.version("tidaleddy")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"

from .control import *
from .mini import mini, parse_mini
from .pattern import *
from .scales import SCALES, SCALE_NAMES, scale
from .utils import *
