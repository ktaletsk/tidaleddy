"""Mini-notation that tidaleddy fixes to match TidalCycles (Vortex differs here).

Each test states the Tidal behaviour, from the Tidal mini-notation reference:
https://tidalcycles.org/docs/reference/mini_notation
"""

from fractions import Fraction

import pytest

from eddy import TimeSpan, mini, n, pure, rand, s


def onsets(pat, cycles=1, start=0):
    events = [e for e in pat.query(TimeSpan(start, start + cycles)) if e.whole.begin == e.part.begin]
    return sorted((e.whole.begin, e.whole.end, str(e.value)) for e in events)


def same(a, b, cycles=1):
    return onsets(mini(a) if isinstance(a, str) else a, cycles) == onsets(mini(b) if isinstance(b, str) else b, cycles)


# --- ? drops each event, not the whole step -----------------------------------


def test_degrade_after_fast_drops_events_one_by_one():
    # Tidal: "bd*8?" plays bd*8 and drops each of the 8 hits with 50% chance.
    assert same("bd*8?", pure("bd").fast(8).degrade_by(Fraction(1, 2)), cycles=16)
    per_cycle = [len(onsets(mini("bd*8?"), 1, c)) for c in range(16)]
    assert any(0 < k < 8 for k in per_cycle), per_cycle


def test_degrade_amount_after_fast():
    assert same("hh*16?0.3", pure("hh").fast(16).degrade_by(0.3), cycles=8)


def test_fast_and_slow_still_take_patterns():
    assert same("bd*<2 3>", pure("bd").fast(mini("<2 3>")), cycles=2)
    assert same("bd*[2 4]", pure("bd").fast(mini("[2 4]")))
    assert same("bd*2!", "bd*2 bd*2")
    assert same("bd*2@3 sn", "[bd bd]@3 sn")


def test_each_degrade_has_its_own_seed():
    # Tidal gives every ? in a pattern a new seed, so two ?s don't drop together.
    pat = mini("[bd*8?, hh*8?]")
    kept = {v: {t for t, _, val in onsets(pat, 16) if val == v} for v in ("bd", "hh")}
    assert kept["bd"] != kept["hh"]
    # the first ? uses seed 0, i.e. plain rand(), as in Tidal
    assert same("hh?", pure("hh").degrade_by(Fraction(1, 2), rand()), cycles=16)
    second = pure("hh").degrade_by(Fraction(1, 2), rand().early(Fraction(1, 10000)))
    assert onsets(mini("[~?, hh?]"), 16) == onsets(second, 16)


def test_seeds_restart_for_every_pattern():
    assert onsets(mini("bd*8?"), 4) == onsets(mini("bd*8?"), 4)


# --- ! repeats ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("bd!3 sn", "bd bd bd sn"),
        ("bd! sn", "bd bd sn"),
        ("bd!! sn", "bd bd bd sn"),
        ("bd!3! sn", "bd bd bd bd sn"),
        ("bd!2", "bd bd"),
        ("bd!1 sn", "bd sn"),
    ],
)
def test_replicate_count(code, expected):
    assert same(code, expected)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("bd ! sn", "bd bd sn"),
        ("bd ! ! sn", "bd bd bd sn"),
        ("[bd !] sn", "[bd bd] sn"),
        ("bd*2 ! sn", "bd*2 bd*2 sn"),
        ("<a b> !", "<a b> <a b>"),
        ("a !", "a a"),
    ],
)
def test_bare_repeat(code, expected):
    assert same(code, expected, cycles=2)


# --- {} polymeter: the first group sets the steps per cycle ------------------


def test_polymeter_steps_default_to_the_first_group():
    assert same("{bd sn, hh hh hh}", "{bd sn, hh hh hh}%2", cycles=3)
    assert onsets(mini("{bd sn, hh hh hh}"), 1) == onsets(mini("[bd sn, hh hh]"), 1)
    assert onsets(mini("{bd sn, hh hh hh}"), 1, 1) == onsets(mini("[bd sn, hh hh]"), 1, 1)
    assert same("{a b c}", "a b c")


def test_polymeter_explicit_steps_unchanged():
    assert same("{a b c, D E}%4", "{a b c, D E}%4", cycles=3)
    assert same("<a b, c d e>", "{a b, c d e}%1", cycles=3)


# --- .. ranges ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("0 .. 3", "0 1 2 3"),
        ("0..3", "0 1 2 3"),
        ("3 .. 0", "3 2 1 0"),
        ("-1 .. 1", "-1 0 1"),
        ("0 .. 3 7", "0 1 2 3 7"),
        ("[0 .. 2]*2", "[0 1 2]*2"),
        ("2 .. 2", "2"),
        ("0 .. 1 . 5", "[0 1] [5]"),
    ],
)
def test_range(code, expected):
    assert same(code, expected)


def test_range_in_controls():
    assert [e.value["n"] for e in n("0 .. 3").query(TimeSpan(0, 1))] == [0, 1, 2, 3]


def test_decimals_are_not_ranges():
    assert [e.value for e in mini("0.5 1").query(TimeSpan(0, 1))] == [0.5, 1]
    assert [e.value for e in mini("0. 1").query(TimeSpan(0, 1))] == [0.0, 1]


# --- documented Tidal behaviour that Vortex already had right -----------------


def test_alternation_advances_on_every_repeat():
    # Tidal: "<a b>*4" is "a b a b". To repeat one value per cycle, use "<a b>!4"-style
    # repeats or .segment(4).
    assert same("<a b>*4", "a b a b")
    assert same(s("<a b>").segment(4), s("a a a a"))


# --- Euclid: as many hits as steps fills every step ----------------------------


def test_euclid_full():
    # Tidal: "bd(8,8)" is bd*8 (Vortex: silence, because 8 % 8 == 0)
    assert same("bd(8,8)", "bd*8")
    assert same("bd(3,3)", "bd*3")
    assert same("bd(3,8)", "bd ~ ~ bd ~ ~ bd ~")


# --- found while fixing: repeated copies are separate steps -------------------


def test_repeated_alternation_plays_the_same_value():
    # Tidal: "<a b>!" is "<a b> <a b>": a a in cycle 0, b b in cycle 1 (Vortex: a b, a b)
    assert same("<a b>!", "<a b> <a b>", cycles=2)
    assert same("<a b>!3 c", "<a b> <a b> <a b> c", cycles=2)


def test_polymeter_counts_ranges_and_repeats_as_steps():
    assert same("{0 .. 3, a b}", "{0 1 2 3, a b}", cycles=2)
    assert same("{a!2 b, c d}", "{a a b, c d}", cycles=2)


def test_degrade_on_repeats_drops_each_copy():
    pat = mini("bd!4?")
    per_cycle = [len(onsets(pat, 1, c)) for c in range(16)]
    assert any(0 < k < 4 for k in per_cycle), per_cycle
