"""Musical scales for Vortex patterns (Vortex has no `scale` function of its own).

    n(scale("minor", "0 2 4 7"))                       # scale degrees -> semitones
    n(scale("minpent", sine().range(0, 10).segment(8)))  # works on signals too

Degrees are floored to whole numbers and wrap into higher/lower octaves.
"""

import math

from .pattern import Pattern, reify

SCALES = {
    "minpent": [0, 3, 5, 7, 10],
    "majpent": [0, 2, 4, 7, 9],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "harmonic": [0, 2, 3, 5, 7, 8, 11],
    "blues": [0, 3, 5, 6, 7, 10],
    "whole": [0, 2, 4, 6, 8, 10],
    "chromatic": list(range(12)),
}
SCALE_NAMES = list(SCALES)


def scale(name: str, pat) -> Pattern:
    """Turn a pattern of scale degrees (0 = root) into semitones."""
    key = str(name).lower().replace(" ", "").replace("_", "")
    if key not in SCALES:
        raise ValueError(f'unknown scale "{name}". Try one of: {", ".join(SCALE_NAMES)}')
    steps = SCALES[key]

    def to_semitones(degree):
        d = math.floor(float(degree) + 1e-9)
        return steps[d % len(steps)] + 12 * (d // len(steps))

    return reify(pat).fmap(to_semitones)
