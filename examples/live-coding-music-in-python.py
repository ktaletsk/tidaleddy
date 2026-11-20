# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "tidaleddy[marimo]>=0.1",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="Live-coding music in Python")


@app.cell(hide_code=True)
def _(mo):
    _video = mo.Html(
        "<iframe src='https://www.youtube-nocookie.com/embed/HkgV_-nJOuE' "
        "title='2 Minute Deep Acid in Strudel (from scratch), by Switch Angel' "
        "style='display:block;width:100%;max-width:720px;aspect-ratio:16/9;border:0;border-radius:12px' "
        "allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' "
        "allowfullscreen></iframe>"
    )
    mo.vstack([
        mo.md(r"""
        # 🌀 Live-coding music in Python

        **Live coding** is making music by writing code while it plays. Here is what that
        looks like: [Switch Angel](https://www.youtube.com/@Switch-Angel) builds a deep acid
        track from scratch in two minutes, in [Strudel](https://strudel.cc), the
        JavaScript sibling of the patterns you'll write below.
        """),
        _video,
        mo.md(r"""
        [eddy](https://ktaletsk.github.io/tidaleddy/) brings the same pattern language,
        from [TidalCycles](https://tidalcycles.org), to Python. You write short patterns of
        rhythm and melody, and eddy turns them into sound, synthesized right here in the
        notebook with numpy.

        This notebook starts with a few small sounds, then shows what Python adds: patterns
        built by code, by a cellular automaton, by your words, and by a loop you bend
        with the mouse.

        **In every box below:** press **▶ Play**, click the code to change it (**↵** applies),
        drag the blue numbers, and click sound names to cycle through them. Changes come in on
        the next loop, without stopping the music. **■ Hush** stops.
        """),
    ])
    return


@app.cell
def _():
    import marimo as mo
    from eddy import TimeSpan, n, s, scale, sequence, stack
    from eddy.marimo import PathPad, Player, Repl, TangleStack, play, render

    return PathPad, Player, Repl, TangleStack, TimeSpan, mo, n, play, render, s, scale, sequence, stack


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. First sounds

    `s("…")` picks sounds by name. Several sounds split the **cycle** (the loop) into
    equal steps: `bd` is a kick drum, `hh` a hi-hat, `sn` a snare.
    """)
    return


@app.cell
def _(Repl):
    Repl('s("bd hh sn hh")')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    `~` is a rest, `[ ]` squeezes several sounds into one step, and `*` repeats a step
    within its slot.
    """)
    return


@app.cell
def _(Repl):
    Repl('s("bd [~ hh] sn hh*3")')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    `< >` plays one item per cycle, taking turns. This box loops four cycles, so you hear
    all four.
    """)
    return


@app.cell
def _(Repl):
    Repl('s("bd <sn cp sn [cp cp]>")', cycles=4)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Give `Repl` several lines and each becomes a **layer** of a `stack(...)`. Click 🔊 to
    mute one. Synths play notes: `n` counts semitones from middle C.
    """)
    return


@app.cell
def _(Repl):
    Repl(
        's("bd(3,8)").gain(1.0)',
        's("~ cp").room(0.3)',
        's("[~ hh]*4").gain(0.45)',
        'n("<[0 3 7 10] [-4 0 3 7]>").s("pluck").room(0.3)',
        cycles=4,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    A little more [mini-notation](https://ktaletsk.github.io/tidaleddy/mini-notation/):
    `(3,8)` is a Euclidean rhythm (3 hits spread over 8 steps), `?0.4` drops 40% of the
    hits at random, and `{ }` lets patterns of different lengths drift against each other.
    """)
    return


@app.cell
def _(Repl):
    Repl('s("[bd(3,8), cp(5,8,2), hh*16?0.4]")', 's("{~ rim, lt mt ht}").gain(0.6)', cycles=4)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Python superpowers

    A pattern is an ordinary Python value. So anything Python can compute, you can play.
    `play(pattern)` gives you a player for any pattern.

    ### Build patterns with code

    A list comprehension makes a whole drum section: hi-hats at 1, 2, 3 and 4 hits per
    cycle, each softer and further to the right.
    """)
    return


@app.cell
def _(play, s, stack):
    hats = stack(*[s("hh").fast(k).gain(1 / k).pan(k / 5) for k in range(1, 5)])
    play(stack(s("bd ~ sn ~"), hats))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Rhythms from a cellular automaton

    An [elementary cellular automaton](https://en.wikipedia.org/wiki/Elementary_cellular_automaton)
    turns a row of cells into the next row by a rule numbered 0 to 255. Each row makes a
    rhythm: a live cell is a rim shot. Four generations, one per cycle. Try rules 30, 90,
    105 and 150.
    """)
    return


@app.cell
def _(mo):
    rule = mo.ui.slider(1, 255, value=90, label="rule", show_value=True)
    rule
    return (rule,)


@app.cell
def _(mo, play, rule, s, stack):
    def automaton(rule: int, width: int = 16, rows: int = 4) -> list[list[int]]:
        """Each row is the next generation, starting from one cell in the middle."""
        row = [0] * width
        row[width // 2] = 1
        out = []
        for _ in range(rows):
            out.append(row)
            row = [
                (rule >> (4 * row[i - 1] + 2 * row[i] + row[(i + 1) % width])) & 1
                for i in range(width)
            ]
        return out


    def draw(grid: list[list[int]]) -> mo.Html:
        """The grid as little squares: teal for a live cell."""
        squares = "".join(
            f"<i style='display:block;aspect-ratio:1;border-radius:3px;"
            f"background:{'#0e8b8b' if cell else '#8882'}'></i>"
            for row in grid for cell in row
        )
        style = "display:grid;grid-template-columns:repeat(16,1fr);gap:3px;max-width:420px"
        return mo.Html(f"<div style='{style}'>{squares}</div>")


    grid = automaton(rule.value)

    # one cycle per row: a rim shot on every live cell
    steps = [" ".join("rim" if cell else "~" for cell in row) for row in grid]
    cells = s("<" + " ".join(f"[{row}]" for row in steps) + ">")
    groove = stack(s("bd*4"), cells.gain(0.8), s("[~ hh]*4").gain(0.35))

    mo.vstack([draw(grid), play(groove, cycles=4)])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Your words as a melody

    Each letter becomes a step in a scale. Type anything and press ↵, then pick a scale.
    """)
    return


@app.cell
def _(mo):
    words = mo.ui.text(value="marimo", label="text")
    mode = mo.ui.dropdown(
        ["minpent", "majpent", "dorian", "phrygian", "blues"],
        value="minpent",
        label="scale",
    )
    mo.hstack([words, mode], justify="start", gap=1)
    return mode, words


@app.cell
def _(mo, mode, n, play, s, scale, sequence, stack, words):
    letters = [c for c in words.value.lower() if c.isalpha()] or ["a"]
    # a=0, b=1 … j=9, then k=0 again: two octaves of a pentatonic scale
    degrees = [(ord(c) - ord("a")) % 10 for c in letters]
    melody = n(scale(mode.value, sequence(*degrees)) - 12).s("pluck").room(0.3)
    mo.vstack([
        mo.md(" ".join(f"`{c}→{d}`" for c, d in zip(letters, degrees))),
        play(stack(melody, s("bd ~ ~ bd ~ ~ bd ~").gain(0.9)), cycles=2),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Patterns are data, too

    `query` returns a pattern's events for a span of time as plain Python objects, so you
    can test patterns, count notes, or draw them however you like.
    """)
    return


@app.cell
def _(TimeSpan, mo, s):
    events = s("bd(3,8) [hh hh] cp").query(TimeSpan(0, 1))
    mo.ui.table(
        [{"start": str(e.whole.begin), "end": str(e.whole.end), "sound": e.value["s"]} for e in events],
        selection=None,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. A loop you can bend

    The pad below is [wigglystuff](https://github.com/koaning/wigglystuff)'s
    `CurveEditor`, turned into a loop. Drag its knots, double-click to add or remove one,
    or roll the 🎲. A dot rides the loop in time with the music, once around per loop
    (drag the `1×` for more laps).

    The stack below the pad can follow the dot:

    | in a layer | what it is |
    |---|---|
    | `path.x` | how far right the dot is, 0 to 1 |
    | `path.y` | how high the dot is, 0 to 1 |
    | `path.knots` | a hit each time the dot passes a knot |

    Here the dot's height plays a melody, its left-right position opens a filter and pans
    the hats, and every knot is a rim shot. Press ▶ on the player, then reshape the loop.
    """)
    return


@app.cell
def _(PathPad, mo):
    pad = mo.ui.anywidget(PathPad(seed=7, knots=6))
    pad
    return (pad,)


@app.cell
def _(pad):
    # the path as patterns; this cell re-runs whenever the loop's shape changes
    path = pad.widget.path(cycles=4)
    return (path,)


@app.cell
def _(TangleStack, mo):
    # one layer per line; "#" starts a layer muted
    editor = mo.ui.anywidget(TangleStack(
        's("bd(<3 5>,8)")',
        's("cp(3,8,2)").room(0.3)',
        's("hh*16").gain(0.5).pan(path.x)',
        'n(scale("minpent", path.y.range(0, 8).segment(8) + "[0 2 4 2]*2")).s("pluck").cutoff(path.x.range(600, 5000)).delay(0.3)',
        's("rim").struct(path.knots).room(0.4).gain(0.9)',
    ))
    editor
    return (editor,)


@app.cell
def _(Player, mo):
    loop_player = Player()
    mo.ui.anywidget(loop_player)
    return (loop_player,)


@app.cell
def _(editor, loop_player, mo, path, render):
    _render = render(editor.widget.pattern(path=path), cycles=4, cps=0.5)
    loop_player.load(_render)
    _errors = len(editor.widget.errors)
    mo.md(
        f"<small>{len(_render.events)} events in a 4-cycle loop"
        + (f" · ⚠️ {_errors} layer(s) skipped, hover the red line" if _errors else "")
        + "</small>"
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Where next

    - [The eddy docs](https://ktaletsk.github.io/tidaleddy/): first sounds, the whole
      mini-notation, and more Python.
    - [The full playground](https://molab.marimo.io/github/ktaletsk/tidaleddy/blob/main/examples/playground.py):
      a bigger live-coding notebook with tempo and loop-length sliders.
    - Locally: `pip install "tidaleddy[marimo]"`, then `marimo edit`.
    - [Source on GitHub](https://github.com/ktaletsk/tidaleddy). eddy's pattern engine
      comes from [Vortex](https://codeberg.org/uzu/vortex), the Python port of TidalCycles.
    """)
    return


if __name__ == "__main__":
    app.run()
