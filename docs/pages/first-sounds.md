---
title: First sounds
nav: First sounds
order: 2
description: Sounds, sequences, rests, layers and notes, one step at a time.
---

# First sounds

<p class="lead">Patterns describe what happens in one <strong>cycle</strong>, a loop that repeats forever. Everything below plays in your browser: edit the code and press ↵, or drag the blue numbers.</p>

## Play a sound

`s("...")` picks a sound by name. With one sound in the quotes, it plays once per cycle.

```eddy
s("bd")
```

eddy has a small synthesized drum kit and a few synths. No samples to download; everything is made with numpy.

| Kind | Names |
|---|---|
| Drums | `bd` kick · `sn` snare · `hh` hi-hat · `oh` open hat · `cp` clap · `rim` · `cb` cowbell · `lt` `mt` `ht` toms · `cr` crash · `perc` |
| Synths | `sine` · `tri` · `saw` · `square` · `supersaw` · `superpiano` · `pluck` · `bass` · `pad` |

## Sequences share the cycle

Write several sounds and they split the cycle into equal steps. Four sounds get a quarter of the cycle each.

```eddy
s("bd hh sn hh")
```

Add a fifth and everything gets a little shorter, but the cycle stays the same length. This is the core idea of Tidal: **the cycle is fixed, the steps divide it.**

```eddy
s("bd hh sn hh cp")
```

!!! tip "Cycles and tempo"
    These examples play at 0.5 cycles per second, so one cycle lasts two seconds. If you think of a cycle as one bar of four beats, that's 120 bpm.

## Rests

A `~` is a step with no sound.

```eddy
s("bd ~ sn ~")
```

## Sub-sequences

Square brackets squeeze a whole sequence into one step.

```eddy
s("bd [hh hh] sn [hh hh hh]")
```

They nest, too: `s("bd [hh [hh hh]] sn hh")`.

## Faster with `*`

`*` plays a step several times within its slot. Drag the numbers to hear the difference.

```eddy
s("bd hh*2 sn hh*3")
```

## One per cycle with `< >`

Angle brackets play one item per cycle, taking turns.

```eddy cycles=4
s("bd <sn cp sn [cp cp]>")
```

## Play together

A comma plays sequences at the same time, each sharing the cycle in its own way.

```eddy
s("[bd ~ sn ~, hh*8]")
```

For longer pieces, put each part on its own line: every line is a **layer**, and the layers stack. Click 🔊 to mute one.

```eddy
s("bd(3,8)").gain(1.0)
s("~ cp").room(0.3)
s("hh*8").gain(0.45)
```

## Notes

Synths play pitches. `n` takes numbers, counted in semitones from middle C (`0`). `note` also takes names like `c3` or `eb4`.

```eddy
n("0 3 7 10").s("pluck")
```

```eddy cycles=4
note("<c3 ab2 f2 g2>").s("bass").legato(0.8)
```

!!! try "Things to try"
    - Change `pluck` to `superpiano` or `saw` (click the name to cycle through synths).
    - Make the chord bigger: `n("0 3 7 10 14")`.
    - Add `.room(0.5)` to the end for reverb, or `.delay(0.3)` for an echo.

## Recap

| Concept | Syntax | Example |
|---|---|---|
| Sound | `s("…")` | `s("bd")` |
| Sequence | spaces | `s("bd hh sn hh")` |
| Rest | `~` | `s("bd ~ sn ~")` |
| Sub-sequence | `[ ]` | `s("bd [hh hh]")` |
| Speed up | `*` | `s("hh*8")` |
| One per cycle | `< >` | `s("bd <sn cp>")` |
| Together | `,` | `s("[bd sn, hh*4]")` |
| Notes | `n`, `note` | `n("0 3 7").s("pluck")` |

Next, [the mini-notation](../mini-notation/) has the rest of the symbols.
