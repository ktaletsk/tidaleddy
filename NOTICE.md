# Notice

tidaleddy contains code from **Vortex**, the Python port of TidalCycles.

- Source: https://codeberg.org/uzu/vortex
- Commit: `aefea84ddde0b5f5e8e94c5a15d00504cb5e2439` (2025-12-26)
- Copyright (C) the Vortex authors ("Tidal Cyclists", vortex@tidalcycles.org)
- Licence: GNU General Public License v3.0 or later ([LICENSE](LICENSE))

tidaleddy as a whole is distributed under the same licence.

## Changes from Vortex (2026-11-20)

Copied, with only the import name changed from `vortex` to `eddy`:

| tidaleddy | Vortex |
|---|---|
| `src/eddy/pattern.py` | `vortex/pattern.py` |
| `src/eddy/control.py` | `vortex/control.py` |
| `src/eddy/euclid.py` | `vortex/euclid.py` |
| `src/eddy/utils.py` | `vortex/utils.py` |
| `tests/upstream/*.py` (except one, below) | `test/*.py` |

`src/eddy/euclid.py` (from `vortex/euclid.py`) also has one fix, listed with the
mini-notation fixes below.

### Mini-notation fixes

The mini-notation files are changed to behave like TidalCycles. Changed lines
are marked with `tidaleddy:` comments, and `tests/test_mini_fixes.py` tests each fix.

| Mini-notation | Vortex | tidaleddy (and Tidal) |
|---|---|---|
| `bd*8?` | `?` applied to the `8`, so all 8 hits or none, per cycle | `?` applies to `bd*8`, dropping hits one by one |
| `bd*8? hh*8?` | every `?` used the same random stream | each `?` has its own seed (Tidal: `rotL (0.0001 * seed) rand`) |
| `bd!3` | 4 copies | 3 copies |
| `<a b>!` | copies joined with `fastcat`, so `a b` | each copy is its own step, so `a a` |
| `bd ! sn` | parse error | a lone `!` repeats the previous step |
| `{bd sn, hh hh hh}` | 1 step per cycle | steps come from the first group (here 2) |
| `0 .. 3` | parse error | `0 1 2 3` |
| `bd(8,8)` | silent (`8 % 8` hits) | 8 hits: every step |

- `src/eddy/mini/grammar.py` (from `vortex/mini/grammar.py`): `*` and `/` take
  a bare value; new `bare_repeat` and `range` rules. The `word` and `ws` regexes
  are also raw strings (`~r"[-\w]+"`, `~r"\s+"`). They match the same text,
  but no longer make Python print a `SyntaxWarning` on every import.
- `src/eddy/mini/interpreter.py` (from `vortex/mini/interpreter.py`): repeat
  counts, repeats as separate steps, per-`?` seeds, polymeter steps and ranges.
- `src/eddy/mini/__init__.py` (from `vortex/mini/__init__.py`): a new visitor
  and interpreter for every pattern, since they now hold per-pattern state.
- `tests/upstream/test_mini_parser.py` (from `test/test_mini_parser.py`): the
  expected trees for `hh!4`, `hh!4!!` and `hh!/2?!` follow Tidal's meaning.

### Other changes

Changed: `src/eddy/__init__.py` is based on `vortex/__init__.py`. It reads its
version from the `tidaleddy` distribution, re-exports the new `scale` helpers,
and drops `vortex_dsl()`.

Left out: `vortex/vortex.py` (a debug-printing helper and a demo script),
`vortex/boot.py`, `vortex/cli.py`, `vortex/gui.py`, `vortex/repl.py`,
`vortex/stream.py` and `vortex/res/`. These are the live-coding GUI, REPL, OSC
streaming and Ableton Link clock.

Each copied file starts with a comment saying where it came from and how it
was changed.

## Added by tidaleddy

`src/eddy/scales.py`, everything in `src/eddy/marimo/`, `tests/test_*.py` and `examples/`.

`eddy.marimo` loads front-end modules from
[wigglystuff](https://github.com/koaning/wigglystuff) (MIT licence) at runtime.
They are not copied into this package.
