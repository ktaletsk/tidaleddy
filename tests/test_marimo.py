"""Tests for eddy.marimo: the synth, the path pad's signals and the stack editor's Python side."""

import base64
import io
import wave
from fractions import Fraction

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("wigglystuff")

from eddy import TimeSpan, n, note, s, silence, stack  # noqa: E402
from eddy.marimo import SOUND_NAMES, PathPad, Player, TangleStack, flatten_value, query_events, render  # noqa: E402
from eddy.marimo.synth import SR  # noqa: E402


def samples(r):
    w = wave.open(io.BytesIO(base64.b64decode(r.wav_b64)))
    assert w.getframerate() == SR and w.getnchannels() == 2
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float).reshape(-1, 2) / 32768


def test_render_length_and_events():
    r = render(stack(s("bd*4"), note("c3 e3").s("bass")), cycles=2, cps=0.5)
    assert r.duration == pytest.approx(4.0)
    assert len(samples(r)) == round(4.0 * SR)
    assert len(r.events) == 12
    assert not r.warnings


def test_render_is_audible_and_does_not_clip():
    a = samples(render(stack(s("bd*4 sn"), n("0 3 7").s("supersaw").room(0.5).delay(0.4)), 2, 0.6))
    assert 0.01 < np.sqrt((a**2).mean()) and np.abs(a).max() < 1.0


def test_render_silence():
    r = render(silence(), 1, 0.5)
    assert r.events == [] and np.abs(samples(r)).max() == 0


def test_render_unknown_sound_warns():
    assert any("zzz" in w for w in render(s("zzz"), 1, 0.5).warnings)


def test_render_rejects_non_patterns():
    with pytest.raises(TypeError):
        render("bd*4", 1, 0.5)


def test_flatten_value():
    assert flatten_value({"s": {"s": "bd", "n": 3}}) == {"s": "bd", "n": 3}
    assert flatten_value({"s": {"s": "bd", "n": 3}, "n": 1}) == {"s": "bd", "n": 1}


def test_query_events_only_onsets():
    assert [float(e.whole.begin) for e in query_events(s("bd ~ sn"), 1)] == [0.0, pytest.approx(2 / 3)]


def test_player_load():
    p = Player()
    p.load(render(s("bd*2"), 1, 0.5))
    assert set(p.clip) == {"wav", "events", "cycles", "cps"} and len(p.clip["events"]) == 2


SQUARE = [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}]


def sampled(sig, cycles, per_cycle):
    """The signal sampled `per_cycle` times per cycle (at the middle of each step), over `cycles` cycles."""
    return [float(e.value) for e in sorted(sig.segment(per_cycle).query(TimeSpan(0, cycles)), key=lambda e: e.whole.begin)]


def test_path_follows_the_knots():
    path = PathPad(SQUARE).path(cycles=4)
    xs = sampled(path.x, 4, 1)       # the middle of each cycle is the middle of one side
    ys = sampled(path.y, 4, 1)
    assert xs == pytest.approx([0.5, 0.8, 0.5, 0.2], abs=0.02)
    assert ys == pytest.approx([0.2, 0.5, 0.8, 0.5], abs=0.02)


def test_path_loops_and_laps():
    pad = PathPad(SQUARE)
    one = sampled(pad.path(2).y, 4, 8)
    assert one[:16] == pytest.approx(one[16:])         # one lap per 2-cycle loop
    assert one[:8] != pytest.approx(one[8:16])
    pad.laps = 2
    two = sampled(pad.path(2).y, 2, 8)
    assert two[:8] == pytest.approx(two[8:])           # two laps per 2-cycle loop


def test_path_knots_are_hits_on_sixteenths():
    hits = [e for e in PathPad(SQUARE).path(cycles=1).knots.query(TimeSpan(0, 1)) if e.whole.begin == e.part.begin]
    assert sorted(e.whole.begin for e in hits) == [0, Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)]


def test_path_uses_browser_samples_when_present():
    pad = PathPad(SQUARE)
    pad.samples = [{"x": 0.5 + 0.3 * np.cos(t), "y": 0.5 + 0.3 * np.sin(t)} for t in np.linspace(0, 2 * np.pi, 129)]
    ys = sampled(pad.path(1).y, 1, 4)
    assert ys == pytest.approx([0.5 + 0.3 * np.sin(np.pi / 4 * k) for k in (1, 3, 5, 7)], abs=0.03)


def test_random_shape_is_seeded():
    assert PathPad(seed=7).points == PathPad(seed=7).points != PathPad(seed=8).points


def test_stack_editor():
    ed = TangleStack('s("bd*4")', '# s("hh*8")', 's("cp")', 'not valid python (', sounds=SOUND_NAMES)
    assert [L["on"] for L in ed.layers] == [True, False, True, True]
    assert "scales" in ed.sounds and "minpent" in ed.sounds["scales"]
    pat = ed.pattern()
    assert list(ed.errors) == ["3"]
    assert sorted(e.value["s"] for e in pat.query(TimeSpan(0, 1))) == ["bd"] * 4 + ["cp"]
    assert ed.code() == 'stack(\n    s("bd*4"),\n    # s("hh*8"),\n    s("cp"),\n    not valid python (,\n)'


def test_stack_editor_extra_names_and_scale():
    ed = TangleStack('n(scale("minor", "0 2")).pan(path.x)', sounds=SOUND_NAMES)
    path = PathPad(SQUARE).path(1)
    pat = ed.pattern(path=path)
    assert not ed.errors
    assert [flatten_value(e.value)["n"] for e in query_events(pat, 1)] == [0, 3]


# --- Repl and play(): what the docs are built from ----------------------------

from eddy.marimo import Repl, play  # noqa: E402


def test_play_returns_a_loaded_player():
    p = play(s("bd*2 sn"), cycles=2)
    assert isinstance(p, Player) and len(p.clip["events"]) == 6 and p.clip["cycles"] == 2


def test_repl_renders_and_follows_edits():
    r = Repl('s("bd hh sn hh")')
    assert r.compact and len(r.clip["events"]) == 8          # 2 cycles by default
    r.layers = [{"code": 's("bd*3")', "on": True}]
    assert len(r.clip["events"]) == 6
    r.layers = [{"code": 's("bd*3")', "on": False}]
    assert r.clip["events"] == []


def test_repl_stack_and_options():
    r = Repl('s("bd sn")', 'n("0 .. 3").s("pluck")', cycles=4, cps=0.8)
    assert not r.compact
    assert r.clip["cycles"] == 4 and r.clip["cps"] == 0.8 and len(r.clip["events"]) == 24
    r.cycles = 1
    assert len(r.clip["events"]) == 6


def test_repl_shows_errors_without_failing():
    r = Repl('s("bd', 's("hh*2")')
    assert list(r.errors) == ["0"] and len(r.clip["events"]) == 4


def test_repl_front_end_runs_both_widgets():
    assert "const STACK = (() => {" in Repl._esm and "const PLAYER = (() => {" in Repl._esm
    module = Repl._esm.split("\n", 1)[1]                    # after the embedded wigglystuff sources
    assert module.count("export default { render };") == 1 and module.count("return { render };") == 2
