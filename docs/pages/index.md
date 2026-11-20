---
title: eddy
nav: Welcome
order: 1
description: TidalCycles patterns in Python. Every example plays in your browser.
---

<div class="hero" markdown="1">

# Make music with <span class="wave">patterns</span>, in Python

<p class="lead">eddy is the pattern engine of TidalCycles, in Python. You describe rhythms and melodies as short patterns, and eddy turns them into sound. Every example on these pages runs in your browser. Edit it, drag its numbers, press ▶.</p>

</div>

```eddy
s("bd hh sn hh")
```

Press **▶ Play**. That's a kick drum (`bd`), a hi-hat (`hh`) and a snare (`sn`), looping.

Now change it while it plays: click the code, swap `sn` for `cp`, and press **↵**. The new beat comes in at the start of the next loop, without stopping the music. That's live coding.

!!! try "Things to try"
    - Click a blue sound name like `hh`: it cycles through the drum kit.
    - Add more sounds: `s("bd hh sn hh bd bd sn hh")`. They squeeze in to share the same time.
    - Put `*2` after a sound, like `hh*2`, to play it twice as fast.

## Where to go next

<div class="cards">
  <a class="card" href="first-sounds/"><div class="emoji">🥁</div><strong>First sounds</strong><span>Sounds, sequences, rests, layers and notes, one small step at a time.</span></a>
  <a class="card" href="mini-notation/"><div class="emoji">🔣</div><strong>Mini-notation</strong><span>Every symbol of the little language inside <code>"…"</code>, with a live example each.</span></a>
  <a class="card" href="python/"><div class="emoji">🐍</div><strong>Python superpowers</strong><span>Build patterns with loops, functions, cellular automata and your own name.</span></a>
</div>

## Why Python?

[TidalCycles](https://tidalcycles.org) is written in Haskell, and [Strudel](https://strudel.cc) brings it to JavaScript. eddy is the Python member of the family, built on the pattern engine of [Vortex](https://codeberg.org/uzu/vortex).

A pattern in eddy is an ordinary Python object. So you can build one with a loop, keep a library of them in a module, generate one from data, or test it with pytest. And inside a [marimo](https://marimo.io) notebook, sliders and text boxes can shape the music while it plays. [Python superpowers](python/) shows what that looks like.

## Try it in a notebook

<div class="molab-card">
  <div class="molab-card-text"><strong>The eddy tour</strong><span>Everything on these pages in one notebook, plus a loop you bend with the mouse. molab is marimo's free cloud notebook service: it installs eddy for you.</span></div>
  <div class="molab-card-links"><a class="molab-button" href="https://molab.marimo.io/github/ktaletsk/tidaleddy/blob/main/examples/tour.py">Open in molab ↗</a><a class="molab-source" href="https://github.com/ktaletsk/tidaleddy/blob/main/examples/tour.py">View source</a></div>
</div>

## Install

eddy needs Python 3.10 or newer. The `marimo` extra adds the synth, the player and the live editor you see here (Python 3.11+).

```bash
pip install "tidaleddy[marimo]"
```

Then, in a marimo notebook:

```python
from eddy.marimo import Repl

Repl('s("bd hh sn hh")')
```

!!! note "How these pages work"
    Each example is a [marimo island](https://docs.marimo.io/guides/exporting/webassembly_html/): a notebook cell running in your browser through [Pyodide](https://pyodide.org), a WebAssembly build of Python. When a page opens, Python starts and installs the latest eddy from PyPI, then the examples come alive. The first visit downloads about 25 MB; after that your browser has it cached. Nothing is sent to a server.
