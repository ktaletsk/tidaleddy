---
title: Mini-notation
nav: Mini-notation
order: 3
description: Every symbol of the mini-notation, with a live example each.
---

# Mini-notation

<p class="lead">The text inside <code>s("…")</code>, <code>n("…")</code> and friends is the <strong>mini-notation</strong>: a tiny language for rhythm, borrowed from TidalCycles. Here is all of it.</p>

| Symbol | Meaning | Example |
|---|---|---|
| `~` | rest | `"bd ~ sn ~"` |
| `[ ]` | group several steps into one | `"bd [hh hh]"` |
| `.` | group, without brackets | `"bd hh . sn sn sn"` |
| `,` | play at the same time | `"[bd sn, hh*4]"` |
| `*` | repeat within the step | `"hh*4"` |
| `/` | stretch over several cycles | `"bd sn/2"` |
| `< >` | one per cycle, taking turns | `"bd <sn cp>"` |
| `!` | repeat as new steps | `"bd!3 sn"`, `"bd ! sn"` |
| `_` | hold the previous step | `"bd _ _ sn"` |
| `@` | give a step more weight | `"bd@3 sn"` |
| `?` | maybe: drop at random | `"hh*8?"`, `"hh*8?0.2"` |
| `\|` | pick one at random each cycle | `"bd \| cp \| sn"` |
| `:` | pick a variant of a sound | `"bd:1 bd:2"` |
| `( )` | Euclidean rhythm | `"bd(3,8)"` |
| `{ }` | polymeter | `"{bd sn, hh hh hh}"` |
| `{ }%n` | polymeter with *n* steps per cycle | `"{bd sn hh}%4"` |
| `..` | a range of numbers | `"0 .. 7"` |

The basics (`~`, `[ ]`, `*`, `< >`, `,`) are on [First sounds](../first-sounds/). The rest are below.

## Repeat: `!` and `*`

They look alike but differ: `*` squeezes copies into the step, while `!` adds new steps. A lone `!` repeats the step before it.

```eddy
s("bd!3 sn")
```

```eddy
s("bd*3 sn")
```

```eddy
s("bd ! cp ! ! sn")
```

## Longer steps: `@` and `_`

`@` gives a step more weight: `bd@3 sn` splits the cycle into 3 + 1 parts. `_` does the same thing one step at a time.

```eddy
note("c3@3 eb3 g3@2 bb3@2").s("supersaw").legato(1).cutoff(1800)
```

## Slower: `/`

`/2` stretches a step over two cycles, so you only hear it every other time.

```eddy cycles=4
s("bd*2 [~ cp/2]")
```

## Random: `?` and `|`

`?` drops each event with a 50% chance; `?0.2` drops 20%. eddy's randomness is worked out from the time in the cycle, so a pattern always makes the same "random" choices, and a groove you like stays put.

```eddy cycles=4
s("[bd*4, hh*16?0.4]")
```

`|` picks one of the options each cycle.

```eddy cycles=4
s("bd*2 [sn | cp | rim*3]")
```

## Euclidean rhythms: `( )`

`bd(3,8)` spreads 3 hits as evenly as possible over 8 steps. Many traditional rhythms are Euclidean: `(3,8)` is the Cuban *tresillo*, `(5,8)` the *cinquillo*. A third number rotates the pattern.

```eddy
s("bd(3,8)")
```

```eddy
s("[bd(3,8), cp(5,8,2), hh*8]")
```

## Polymeter: `{ }`

Curly brackets give every part the same *step length* rather than the same *cycle length*. The first part sets the step: here two steps per cycle, so the three-step hi-hat pattern drifts against it and lines up again every three cycles.

```eddy cycles=3
s("{bd sn, hh oh rim}")
```

With `%n` you choose the steps per cycle yourself.

```eddy
s("{bd cp hh}%8")
```

## Ranges: `..`

`0 .. 7` counts from 0 to 7, one step each. Handy for scales and arpeggios.

```eddy
n("0 .. 7").s("pluck")
```

## Variants: `:`

`:n` picks a variant of a sound. In eddy's synthesized kit, variants change the tuning and decay.

```eddy
s("bd:0 bd:1 bd:2 bd:3")
```

!!! note "eddy and Vortex"
    eddy started from Vortex's mini-notation and fixed a few places where it behaved differently from TidalCycles: `?` after `*`, `!n`, a lone `!`, `{ }` without `%`, and `..`. If you know Tidal or Strudel, things should work the way you expect.
