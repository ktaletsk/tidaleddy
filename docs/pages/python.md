---
title: Python superpowers
nav: Python superpowers
order: 4
description: Patterns are Python objects. Build them with loops, functions, cellular automata and text.
---

# Python superpowers

<p class="lead">In eddy a pattern is an ordinary Python value. Anything Python can compute, you can play. The code on this page runs live in your browser; move the sliders and type in the boxes.</p>

On this page each example shows its Python code with the result underneath. Together they work like the cells of one [marimo](https://marimo.io) notebook: later examples can use names from earlier ones, and when a slider moves, everything that depends on it runs again.

```python live
import marimo as mo
from eddy import n, s, scale, sequence, stack
from eddy.marimo import play
```

## Build patterns with code

`play(pattern)` gives you a player for any pattern. And since patterns are values, a list comprehension can make a whole drum section: here, hi-hats at 1, 2, 3 and 4 hits per cycle, each softer than the last.

```python live
hats = stack(*[s("hh").fast(k).gain(1 / k).pan(k / 5) for k in range(1, 5)])
play(stack(s("bd ~ sn ~"), hats))
```

## Rhythms from a cellular automaton

An [elementary cellular automaton](https://en.wikipedia.org/wiki/Elementary_cellular_automaton) turns one row of cells into the next by a simple rule, numbered 0 to 255. Each row makes a good rhythm: a cell that's on is a hit. Pick a rule and listen to four generations, one per cycle.

```python live
rule = mo.ui.slider(1, 255, value=90, label="rule", show_value=True)
rule
```

```python live
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
        f"<i style='background:{'#0e8b8b' if cell else '#8882'}'></i>"
        for row in grid for cell in row
    )
    return mo.Html(f"<div class='ca-grid'>{squares}</div>")


grid = automaton(rule.value)

# one cycle per row: a rim shot on every live cell
steps = [" ".join("rim" if cell else "~" for cell in row) for row in grid]
cells = s("<" + " ".join(f"[{row}]" for row in steps) + ">")
groove = stack(s("bd*4"), cells.gain(0.8), s("[~ hh]*4").gain(0.35))

mo.vstack([draw(grid), play(groove, cycles=4)])
```

Rules 30, 90, 105 and 150 are good places to start. Rule 90 draws a Sierpiński triangle, which you can hear as rim shots spreading outwards.

## Your words as a melody

Each letter becomes a step in a scale. Type anything and press ↵, then pick a scale.

```python live
words = mo.ui.text(value="marimo", label="text")
mode = mo.ui.dropdown(
    ["minpent", "majpent", "dorian", "phrygian", "blues"],
    value="minpent",
    label="scale",
)
mo.hstack([words, mode], justify="start", gap=1)
```

```python live
letters = [c for c in words.value.lower() if c.isalpha()] or ["a"]
# a=0, b=1 … j=9, then k=0 again: two octaves of a pentatonic scale
degrees = [(ord(c) - ord("a")) % 10 for c in letters]
melody = n(scale(mode.value, sequence(*degrees)) - 12).s("pluck").room(0.3)
mo.vstack([
    mo.md(" ".join(f"`{c}→{d}`" for c, d in zip(letters, degrees))),
    play(stack(melody, s("bd ~ ~ bd ~ ~ bd ~").gain(0.9)), cycles=2),
])
```

## Patterns are data, too

A pattern can also be *asked* what it does. `query` returns its events for a span of time, as plain Python objects, so you can test patterns, count notes or draw them however you like.

```python live
from eddy import TimeSpan

events = s("bd(3,8) [hh hh] cp").query(TimeSpan(0, 1))
mo.ui.table(
    [{"start": str(e.whole.begin), "end": str(e.whole.end), "sound": e.value["s"]} for e in events],
    selection=None,
)
```

## Take it further in a notebook

These examples, and a loop you bend with the mouse that the music follows, are in one notebook. Open it on molab to change any of the code, then make it your own: generate patterns from data with pandas, from images with numpy, or from the weather.

<div class="molab-card">
  <div class="molab-card-text"><strong>Live-coding music in Python</strong><span>Edit the Python, add cells, and keep a copy. Runs in the cloud with molab; nothing to install.</span></div>
  <div class="molab-card-links"><a class="molab-button" href="https://molab.marimo.io/github/ktaletsk/tidaleddy/blob/main/examples/live-coding-music-in-python.py">Open in molab ↗</a><a class="molab-source" href="https://github.com/ktaletsk/tidaleddy/blob/main/examples/live-coding-music-in-python.py">View source</a></div>
</div>
