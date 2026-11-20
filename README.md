# tidaleddy

**The TidalCycles pattern engine from [Vortex](https://codeberg.org/uzu/vortex), without the GUI or OSC. Plus a playground for hearing patterns in [marimo](https://marimo.io) notebooks.**

Vortex is the Python port of [TidalCycles](https://tidalcycles.org). Its pattern engine is pure Python, but installing Vortex also installs a Qt editor, OSC networking and an Ableton Link clock. Its last PyPI release (2022) also predates Python 3.11. `tidaleddy` packages just the engine, so it installs anywhere Python runs:

```bash
pip install tidaleddy
```

```python
from eddy import n, s, stack, scale, TimeSpan

pat = stack(
    s("bd(3,8) [~ sn]"),
    n(scale("minor", "<0 2> 4 [6 7]")).s("superpiano"),
)
for event in pat.query(TimeSpan(0, 1)):   # the events in the first cycle
    print(event)
```

> **This is an unofficial repackaging, not the Vortex project.** Credit for the pattern engine goes to the Vortex authors. Please report engine bugs [upstream](https://codeberg.org/uzu/vortex/issues). If Vortex makes its GUI optional and publishes to PyPI again, this package will point you there.

## Hear it in marimo

The `marimo` extra adds `eddy.marimo`. Everything in it is synthesized with numpy, so no SuperCollider is needed. It works locally and in hosted notebooks like [molab](https://molab.marimo.io).

```bash
pip install "tidaleddy[marimo]"
```

The core works on Python 3.10+. The `marimo` extra needs Python 3.11+ because wigglystuff does.

| | |
|---|---|
| `Repl('s("bd hh sn hh")')` | a live-coding box: edit the code, drag its numbers, press ▶. Needs nothing else in the notebook |
| `play(pattern)` | a player for any pattern you build in Python |
| `render(pat, cycles, cps)` | renders a pattern to a seamless stereo loop: drums, synths, filters, reverb and delay |
| `Player` | ▶ / ■ buttons and a pianoroll. Swaps in a new render on the next cycle, so the music never stops |
| `TangleStack` | a `stack(...)` code editor: type code, drag numbers, click sound and scale names ([wigglystuff](https://github.com/koaning/wigglystuff) Tangle widgets) |
| `PathPad` | a loop you bend by dragging knots. A dot rides it in time with the music, and patterns follow it via `path.x`, `path.y`, `path.knots` |

See [`examples/playground.py`](examples/playground.py) for a complete notebook. It lists its own dependencies, so marimo can install them in a sandbox:

```bash
marimo edit --sandbox examples/playground.py
```

## Documentation

The docs are Markdown pages in [`docs/pages`](docs/pages) whose examples run in the browser as [marimo islands](https://docs.marimo.io/guides/exporting/webassembly_html/) on Pyodide. Build them into a static site and serve it with anything:

```bash
.venv/bin/python docs/build.py
python -m http.server -d docs/_site
```

[`docs/build.py`](docs/build.py) explains the page format: ```` ```eddy ```` blocks become editable, playable examples, and ```` ```python live ```` blocks run Python and show the result.

### Publishing on GitHub Pages

[`.github/workflows/docs.yml`](.github/workflows/docs.yml) runs the tests, builds the docs and deploys them on every push to `main` (or by hand, from the Actions tab). Turn it on once, in the repository's **Settings → Pages → Build and deployment → Source: GitHub Actions**. The site then lives at `https://<user>.github.io/<repo>/`.

On GitHub the build also adds a link to the repository in the header and an "Edit this page" link to every page. To get those elsewhere, set `EDDY_REPO_URL` (and `EDDY_REPO_BRANCH` if it isn't `main`) when building.

The install step uses `uv.lock`, so after changing dependencies run `uv lock` and commit the lockfile.

## Developing

```bash
uv venv && uv pip install -e ".[marimo]" pytest marimo
.venv/bin/python -m pytest                 # Vortex's own engine tests plus tidaleddy's
.venv/bin/marimo edit examples/playground.py
```

## What's in the package

| | Origin |
|---|---|
| `eddy` (patterns, controls, mini-notation, euclid) | Vortex, [commit `aefea84`](https://codeberg.org/uzu/vortex/src/commit/aefea84ddde0b5f5e8e94c5a15d00504cb5e2439) (2025-12-26). The import name changed, and the mini-notation is fixed to match Tidal (below) |
| `eddy.scale` | new in tidaleddy |
| `eddy.marimo` | new in tidaleddy |
| left out | Vortex's GUI, REPL, CLI, OSC streaming and Link clock (`gui`, `repl`, `cli`, `boot`, `stream`), and `vortex_dsl()` |

The import name is `eddy` so the package can sit next to a real Vortex install without clashing. Code written for Vortex works if you change `vortex` to `eddy` in its imports, except where it relied on the mini-notation bugs below. [NOTICE.md](NOTICE.md) has the details of what changed.

### Mini-notation fixes

These behave like TidalCycles in eddy, but not in Vortex 0.1 / `aefea84`:

| | Vortex | eddy and Tidal |
|---|---|---|
| `"bd*8?"` | all 8 hits or none, per cycle | each hit dropped separately |
| `"bd*8? hh*8?"` | both `?` drop together | each `?` has its own seed |
| `"bd!3 sn"` | 4 bd | 3 bd |
| `"<a b>!"` | `a b` | `a a` |
| `"bd ! sn"` | parse error | `bd bd sn` |
| `"{bd sn, hh hh hh}"` | 1 step per cycle | 2 steps, set by the first group |
| `"0 .. 3"` | parse error | `0 1 2 3` |
| `"bd(8,8)"` | silent | 8 hits |

### Still different from Tidal / Strudel

- **Signals are functions:** `sine()`, not `sine`.
- **No arithmetic on control patterns:** `n("0 2") + 12` fails. Add the numbers inside instead: `n(sequence(0, 2) + 12)`.
- **`"<a b>*8"` plays `a b a b a b a b`.** That's how Tidal works too, not a bug. To play `a` eight times in one cycle and `b` eight times in the next, use `s("<a b>").segment(8)`.

## Licence

GPL-3.0-or-later, like Vortex. See [LICENSE](LICENSE).
