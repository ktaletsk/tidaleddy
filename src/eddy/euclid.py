# Copied from Vortex (https://codeberg.org/uzu/vortex), commit aefea84ddde0b5f5e8e94c5a15d00504cb5e2439.
# Copyright (C) the Vortex authors ("Tidal Cyclists"). Licensed under GPL-3.0-or-later.
# Modified for tidaleddy, 2026-11-20: imports renamed from `vortex` to `eddy`; `bjorklund(n, n)`
# gives n hits instead of none (marked `tidaleddy:`).

from typing import List

from .utils import flatten


def bjorklund(k: int, n: int, safe=True) -> List[int]:
    """Applies Bjorklund's algorithm for generating an euclidean rhythm sequence"""

    if not safe:
        if k > n:
            raise ValueError("k should be <= n")
        if k < 0 or n < 0:
            raise ValueError("k and n should be non-negative integers")

    # Instead of throwing exception, make sure `n` and `k are valid by taking
    # the absolute value of `n`` and `k % n` respectively.
    n = abs(n)
    # tidaleddy: k == n means every step (Vortex's `k % n` made "bd(8,8)" silent)
    k = n if abs(k) == n else abs(k % n)

    if n == 0 or k == 0:
        return []

    bins = [[1] for _ in range(k)]
    if n == k:
        return flatten(bins)
    remainders = [[0] for _ in range(n - k)]

    while len(remainders) > 1:
        new_remainders = []
        for i, bin in enumerate(bins):
            if not remainders:
                new_remainders.append(bin)
            else:
                bin += remainders.pop(0)
                bins[i] = bin

        if new_remainders:
            bins = bins[: -len(new_remainders)]
            remainders = new_remainders

    return flatten(bins + remainders)
