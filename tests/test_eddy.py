"""Tests for what tidaleddy adds on top of the Vortex engine (scales, the light package itself)."""

import subprocess
import sys
from fractions import Fraction

import pytest

import eddy
from eddy import TimeSpan, n, s, scale, stack


def values(pat, begin=0, end=1):
    return [e.value for e in sorted(pat.query(TimeSpan(begin, end)), key=lambda e: e.whole.begin)]


def test_engine_basics():
    events = s("bd(3,8) sn").query(TimeSpan(0, 1))
    assert sorted((e.whole.begin, e.value["s"]) for e in events) == [
        (Fraction(0), "bd"), (Fraction(3, 16), "bd"), (Fraction(3, 8), "bd"), (Fraction(1, 2), "sn"),
    ]
    assert len(stack(s("hh*8"), n("0 3")).query(TimeSpan(0, 1))) == 10


def test_core_import_is_light():
    """`import eddy` must not pull in numpy, scipy, anywidget, Qt or OSC libraries."""
    code = (
        "import sys, eddy\n"
        "heavy = {'numpy', 'scipy', 'anywidget', 'wigglystuff', 'PyQt6', 'liblo', 'pyliblo3', 'link', 'IPython'}\n"
        "print(sorted(heavy & {m.split('.')[0] for m in sys.modules}))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def test_version():
    assert eddy.__version__ != "unknown"


@pytest.mark.parametrize(
    ("name", "degrees", "expected"),
    [
        ("minor", "0 2 4 7", [0, 3, 7, 12]),
        ("major", "0 1 2 3 4 5 6 7", [0, 2, 4, 5, 7, 9, 11, 12]),
        ("minpent", "-1 5 9", [-2, 12, 22]),
        ("chromatic", "13", [13]),
    ],
)
def test_scale(name, degrees, expected):
    assert values(scale(name, degrees)) == expected


def test_scale_floors_signals_and_accepts_aliases():
    assert values(scale("Min_Pent", eddy.pure(2.9))) == [5]
    assert values(scale("minpent", eddy.saw().range(0, 5).segment(5))) == [0, 3, 5, 7, 10]


def test_scale_unknown():
    with pytest.raises(ValueError, match="unknown scale"):
        scale("nope", "0")


def test_scale_names():
    assert set(eddy.SCALE_NAMES) == set(eddy.SCALES)
    assert all(steps[0] == 0 and steps == sorted(steps) and steps[-1] < 12 for steps in eddy.SCALES.values())
