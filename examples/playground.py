# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "tidaleddy[marimo]>=0.1,<0.2",
#     "wigglystuff>=0.6,<0.7",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="eddy playground")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 🌀 eddy playground

    [eddy](https://pypi.org/project/tidaleddy/) is the TidalCycles pattern engine from
    [Vortex](https://codeberg.org/uzu/vortex), the Python port of TidalCycles (Strudel is
    its JavaScript sibling). Normally Tidal sends OSC to SuperCollider/SuperDirt. Here a
    small numpy synth (`eddy.marimo`) renders the pattern straight to audio instead, so
    nothing else needs installing.

    **How to play:** press **▶ Play**, then play with the code below it. It's a
    [Tangle](https://worrydream.com/Tangle/)-style code editor built from
    [wigglystuff](https://github.com/koaning/wigglystuff) widgets:

    - **type:** click any code to edit that line. **↵** applies it, **esc** cancels, **↑ ↓** move between lines.
      "+ add a layer" adds a line, and an empty line is removed. **✎ edit as text** edits (or pastes) the whole stack.
    - **drag** the blue numbers (shift = ×10, alt = ×0.1, or click one to type a value)
    - **click** a sound or scale name to cycle it, or 🔊 to mute a layer
    - **shape the path:** the pad above the code is a loop you bend by dragging its knots. A dot rides it in
      time with the music, and layers can follow the dot with `path.x`, `path.y` and `path.knots`.

    Every change comes in on the next cycle and playback doesn't stop. **■ Hush** stops it.
    Edits live in the widget. To keep them, **copy** the stack as code, or paste it into
    the editor cell's source. Re-running that cell resets it.
    """)
    return


@app.cell(hide_code=True)
def _():
    # The eddy vocabulary (marimo doesn't allow `import *`, so it's spelled out)
    from eddy import (
        # sound + controls
        s, sound, n, note, octave, gain, amp, pan, speed, legato, sustain,
        attack, release, cutoff, hcutoff, shape, crush, coarse,
        room, size, delay, delaytime, delayfeedback,
        # building patterns
        stack, sequence, fastcat, slowcat, cat, timecat, polymeter, polyrhythm,
        pure, silence, run, scan, mini,
        # randomness + continuous signals (call them: sine(), rand() ...)
        rand, irand, perlin, choose, randcat, wchoose, sine, saw, tri, square,
        # transformations usable as functions: .every(2, fast(2))
        fast, slow, rev, jux, early, late, degrade,
        Pattern, TimeSpan, scale,
    )
    from eddy.marimo import SOUND_NAMES, PathPad, Player, TangleStack, flatten_value, query_events, render
    from wigglystuff import CopyToClipboard

    return (
        CopyToClipboard,
        PathPad,
        Player,
        SOUND_NAMES,
        TangleStack,
        flatten_value,
        query_events,
        render,
        scale,
        silence,
        stack,
    )


@app.cell
def _(mo):
    cps = mo.ui.slider(0.25, 1.25, step=0.025, value=0.5, label="cps", show_value=True)
    cycles = mo.ui.slider(1, 16, step=1, value=4, label="loop (cycles)", show_value=True)
    mo.hstack([cps, cycles], justify="start", gap=2)
    return cps, cycles


@app.cell
def _(Player, mo):
    player = Player()
    mo.ui.anywidget(player)
    return (player,)


@app.cell(hide_code=True)
def _(PathPad, mo):
    # The path pad is wigglystuff's CurveEditor, with its dot driven by the audio clock.
    # Change the seed for a different starting shape, or pass points=[{"x": .., "y": ..}, ...].
    pad = mo.ui.anywidget(PathPad(seed=-387567788, knots=6))
    mo.hstack(
        [
            pad,
            mo.md(r"""
            **The path.** Bend the loop and a dot rides it in time with the
            music, once around per loop. Any layer can follow the dot:

            | in a layer | what it is |
            |---|---|
            | `path.x` | how far right the dot is, 0 to 1 |
            | `path.y` | how high the dot is, 0 to 1 |
            | `path.knots` | a hit each time the dot passes a knot |

            Both `path.x` and `path.y` work like `sine()`: scale them with
            `.range(lo, hi)`, turn them into notes with `.segment(8)`.

            In the stack below, the dot's height moves a little arpeggio up
            and down a scale, its left-right position opens the filter and
            pans the hats, and every knot is a rim shot.
            """).style({"max-width": "360px"}),
        ],
        justify="start",
        align="start",
        gap=1.5,
    )
    return (pad,)


@app.cell(hide_code=True)
def _(cycles, pad):
    # The path as eddy patterns. Referencing `pad` re-runs this whenever the shape changes.
    path = pad.widget.path(cycles.value)
    return (path,)


@app.cell(hide_code=True)
def _(SOUND_NAMES, TangleStack, mo):
    # One layer per line. A leading "#" starts the layer muted.
    editor = mo.ui.anywidget(TangleStack(
        's("bd(<3 5>,8)")',
        's("cp(3,8,2)").room(0.3)',
        's("hh*16").gain(rand().range(0.3, 0.8)).pan(path.x)',
        'n(scale("minpent", path.y.range(0, 8).segment(8) + "[0 2 4 2]*2")).s("pluck").cutoff(path.x.range(600, 5000)).delay(0.3).room(0.3)',
        's("rim").struct(path.knots).room(0.4).gain(0.9)',
        sounds=SOUND_NAMES,
    ))
    editor
    return (editor,)


@app.cell
def _(silence):
    # ✏️ Free-form eddy code, stacked on top of the editor (Cmd/Ctrl+Enter to run)
    extra = silence()
    return (extra,)


@app.cell(hide_code=True)
def _(CopyToClipboard, editor, extra, mo, path, stack):
    pat = stack(editor.widget.pattern(path=path), extra)
    _errors = editor.widget.errors
    mo.hstack(
        [
            mo.md(f"<small>⚠️ {len(_errors)} layer(s) skipped. Hover the red line for the error.</small>")
            if _errors
            else mo.md("<small>Copy the current stack as plain eddy code, e.g. into the free-form cell →</small>"),
            CopyToClipboard(text_to_copy="pat = " + editor.widget.code()),
        ],
        justify="space-between",
        align="center",
    )
    return (pat,)


@app.cell(hide_code=True)
def _(cps, cycles, editor, mo, pad, pat, player, render):
    import time

    # While a number or a knot is being dragged, re-render at most ~3x per second.
    # The player only swaps on cycle boundaries anyway, and the release always renders.
    _now = time.monotonic()
    mo.stop(
        (editor.widget.dragging or pad.widget.dragging) and _now - getattr(player, "last_render", 0) < 0.3,
        mo.md("<small>scrubbing…</small>"),
    )
    player.last_render = _now
    _r = render(pat, cycles.value, cps.value)
    player.load(_r)
    _msg = f"{len(_r.events)} events · {_r.duration:.1f}s loop · ≈ {cps.value * 240:.0f} bpm"
    (
        mo.callout(mo.md("\n\n".join(["⚠️ " + w for w in _r.warnings] + [_msg])), kind="warn")
        if _r.warnings
        else mo.md(f"<small>{_msg}</small>")
    )
    return


@app.cell(hide_code=True)
def _(flatten_value, mo, pat, query_events):
    _rows = [
        {
            "begin": str(e.whole.begin),
            "end": str(e.whole.end),
            **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in flatten_value(e.value).items()},
        }
        for e in query_events(pat, 1)
    ]
    mo.accordion({f"🔎 Events in cycle 0 ({len(_rows)})": mo.ui.table(_rows, page_size=12, selection=None)})
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Cheat sheet

    | | |
    |---|---|
    | **Drums** | `bd` `sn`/`sd` `hh` `oh` `cp` `rim` `cb` `lt` `mt` `ht` `cr` `perc`. Use `:n` or `.n()` for variants, e.g. `s("bd:2")` |
    | **Synths** | `sine` `tri` `saw` `square` `supersaw` `superpiano` `pluck` `bass` `pad`. Pitch comes from `note` and/or `n` |
    | **Notes** | Tidal convention: `0` = `c5` = middle C. Names look like `c`, `eb4`, `fs6`; numbers are semitones |
    | **Controls** | `gain` `pan` `speed` `legato` `sustain` `attack` `release` `octave` `cutoff` `hcutoff` (Hz) `shape` `crush` `coarse` `room` `size` `delay` `delaytime` (s) `delayfeedback` |
    | **Mini-notation** | `~` rest · `[a b]` group · `a*3` · `a/2` · `<a b>` alternate · `a(3,8)` euclid · `a@3` · `a _ b` · `[a, b]` stack · `a . b` · `a?` maybe · `a!3` repeat · `a | b` either · `{a b, c d e}` polymeter · `0 .. 7` range |
    | **Functions** | `.fast` `.slow` `.rev` `.every(n, f)` `.jux(rev)` `.iter(4)` `.superimpose(f)` `.degrade_by(.3)` `.sometimes(f)` `.segment(n)` `.struct()` `.mask()` `.early` `.late` |
    | **Signals** | `sine()` `saw()` `tri()` `square()` `rand()` `perlin()` `irand(8)`, all scaled with `.range(lo, hi)` |
    | **The path** | `path.x` `path.y` are signals too (0 to 1, one lap of the path per loop). `path.knots` is a hit at every knot, for `.struct(path.knots)` |
    | **Scales** | `scale("minor", "0 2 4 7")` turns scale steps into notes: `minpent` `majpent` `minor` `major` `dorian` `phrygian` `lydian` `mixolydian` `harmonic` `blues` `whole` `chromatic` |

    **How this differs from Strudel:** methods are snake_case (`degrade_by`, not
    `degradeBy`), signals are functions (`sine()`, not `sine`), and lambdas take
    the place of arrow functions (`.sometimes(lambda p: p.speed(2))`).

    **Engine quirks to know about:** you can't do arithmetic on control patterns
    (`n("0 2") + 12` fails; write `n(sequence(0, 2) + 12)`), and `"<a b>*8"` plays
    `a b a b …` as in Tidal (use `s("<a b>").segment(8)` to hold each value for a cycle).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Things to try

    Paste any of these into the free-form cell or mute the editor's layers to hear them alone:

    ```python
    # the path as a bassline: the dot's height picks one of five low notes, twice per cycle
    extra = n(scale("minpent", path.y.range(0, 5).segment(2))).s("bass").octave(3).legato(0.8)

    # every knot of the path plays a chord
    extra = note("[c,eb,g]").s("superpiano").struct(path.knots).room(0.4)

    # acid-ish bass with a cutoff sweep and some distortion
    extra = n("0 0 12 0 3 0 10 7").s("saw").octave(3).legato(0.5) \
        .cutoff(sine().range(200, 3000).slow(2)).shape(0.4)

    # stereo trick: jux plays a reversed copy on the right
    extra = n(run(8)).s("pluck").jux(rev).room(0.4)

    # randomness with a fixed seed per cycle, so every loop sounds the same
    extra = n(irand(12).segment(8)).s("superpiano").sometimes(lambda p: p.octave(6)).room(0.4)
    ```
    """)
    return


if __name__ == "__main__":
    app.run()
