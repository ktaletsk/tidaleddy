"""eddy.marimo.synth: a tiny numpy stand-in for SuperDirt.

TidalCycles (and Vortex, its Python port) normally send OSC messages to
SuperCollider/SuperDirt. This module renders an eddy pattern straight to a
seamless stereo audio loop instead, so you can play with patterns in a
notebook without installing SuperCollider.

Everything here is synthesized; there are no samples. It's a toy, but it
supports the most common controls:

    s / sound, n, note, octave, gain, amp, velocity, pan, speed, legato,
    attack, release, sustain, cutoff, hcutoff, shape, crush, coarse,
    room, size, delay, delaytime, delayfeedback
"""

from __future__ import annotations

import base64
import io
import math
import re
import wave
from dataclasses import dataclass, field
from fractions import Fraction
from functools import lru_cache

import numpy as np
from scipy import signal as sps
from eddy import Pattern, TimeSpan

SR = 44100
MASTER_GAIN = 0.45

# --------------------------------------------------------------------------
# value helpers
# --------------------------------------------------------------------------


def flatten_value(value) -> dict:
    """Flatten event values.

    `s("bd:3")` yields `{"s": {"s": "bd", "n": 3}}`; we turn that into
    `{"s": "bd", "n": 3}`. Plain keys win over nested ones, so
    `s("bd:3").n(1)` gives n=1 like Tidal.
    """
    if not isinstance(value, dict):
        return {"s": str(value)}
    out: dict = {}
    for v in value.values():
        if isinstance(v, dict):
            out.update(flatten_value(v))
    for k, v in value.items():
        if not isinstance(v, dict):
            out[k] = v
    return out


_NOTE_RE = re.compile(r"^([a-gA-G])([sf#b]*)(-?\d+)?$")
_PITCH_CLASS = dict(c=0, d=2, e=4, f=5, g=7, a=9, b=11)
_NAMES = ["c", "cs", "d", "ds", "e", "f", "fs", "g", "gs", "a", "as", "b"]


def note_number(x) -> float:
    """Tidal-style note number: 0 = c5 = middle C (MIDI 60)."""
    if isinstance(x, (int, float, Fraction)):
        return float(x)
    m = _NOTE_RE.match(str(x).strip())
    if not m:
        raise ValueError(f"can't parse note name {x!r} (try e.g. 'c', 'eb4', 'fs6')")
    pc = _PITCH_CLASS[m[1].lower()] + sum(1 if c in "s#" else -1 for c in m[2])
    octave = int(m[3]) if m[3] else 5
    return pc + (octave - 5) * 12


def midi_name(midi: float) -> str:
    """Name a MIDI note the Tidal way (MIDI 60 -> 'c5')."""
    m = int(round(midi))
    return f"{_NAMES[m % 12]}{m // 12}"


def _num(v, default: float) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# drum voices (deterministic, cached)
# --------------------------------------------------------------------------


def _t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def _noise(seed: int, length: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(-1, 1, length)


@lru_cache(maxsize=None)
def _sos(kind: str, freq: float | tuple, order: int = 2):
    return sps.butter(order, freq, btype=kind, fs=SR, output="sos")


def _filt(x, kind, freq, order=2):
    if isinstance(freq, tuple):
        freq = tuple(min(max(f, 20.0), SR / 2 - 100) for f in freq)
    else:
        freq = min(max(freq, 20.0), SR / 2 - 100)
    return sps.sosfilt(_sos(kind, freq, order), x)


def _bd(v):
    scale = [1.0, 0.85, 1.25, 0.7, 1.1][v % 5]
    decay = [0.28, 0.4, 0.18, 0.55, 0.3][v % 5]
    t = _t(decay * 3.5)
    f = (45 + 115 * np.exp(-t / 0.035)) * scale
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay)
    click = _noise(1 + v, len(t)) * np.exp(-t / 0.002) * 0.35
    return np.tanh(1.6 * (body + click))


def _sn(v):
    tone_f = [185, 220, 160, 250][v % 4]
    t = _t(0.4)
    tone = np.sin(2 * np.pi * tone_f * t) * np.exp(-t / 0.06) * 0.6
    nz = _filt(_noise(10 + v, len(t)), "highpass", 1200 + 300 * (v % 3))
    return tone + nz * np.exp(-t / (0.09 + 0.03 * (v % 3)))


def _hh(v, open_=False):
    decay = (0.18 + 0.08 * (v % 3)) if open_ else (0.018 + 0.008 * (v % 3))
    t = _t(decay * 5)
    nz = _filt(_noise(20 + v + 50 * open_, len(t)), "highpass", 7000 - 800 * (v % 3))
    return nz * np.exp(-t / decay) * 0.8


def _cp(v):
    t = _t(0.5)
    nz = _filt(_noise(30 + v, len(t)), "bandpass", (900.0 + 150 * (v % 3), 2600.0))
    env = np.zeros_like(t)
    for i, ti in enumerate([0.0, 0.011, 0.022]):
        on = t >= ti
        env[on] += np.exp(-(t[on] - ti) / 0.004) * (0.8 if i < 2 else 1.0)
    on = t >= 0.03
    env[on] += np.exp(-(t[on] - 0.03) / (0.09 + 0.03 * (v % 2)))
    return nz * env * 1.6


def _rim(v):
    t = _t(0.07)
    tone = np.sin(2 * np.pi * (1700 + 200 * (v % 3)) * t) * np.exp(-t / 0.01)
    return (tone + _noise(40 + v, len(t)) * np.exp(-t / 0.003)) * 0.7


def _cb(v):
    t = _t(0.5)
    x = sps.square(2 * np.pi * 540 * t) + sps.square(2 * np.pi * 800 * t)
    return _filt(x, "bandpass", (500.0, 2500.0)) * np.exp(-t / (0.09 + 0.04 * (v % 3))) * 0.4


def _tom(base):
    def make(v):
        f0 = base * [1.0, 1.12, 0.9, 1.25][v % 4]
        t = _t(0.9)
        f = f0 * (1 + 0.6 * np.exp(-t / 0.05))
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22) * 0.9

    return make


def _cr(v):
    t = _t(2.5)
    nz = _filt(_noise(60 + v, len(t)), "highpass", 4500)
    return nz * np.exp(-t / (0.7 + 0.2 * (v % 3))) * 0.45


def _perc(v):
    t = _t(0.25)
    f = 600 * (1 + v % 7 * 0.15) * (1 + 1.5 * np.exp(-t / 0.01))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.05) * 0.7


DRUMS = {
    "bd": _bd,
    "sn": _sn,
    "sd": _sn,
    "hh": _hh,
    "oh": lambda v: _hh(v, open_=True),
    "cp": _cp,
    "rim": _rim,
    "cb": _cb,
    "lt": _tom(95),
    "mt": _tom(135),
    "ht": _tom(190),
    "cr": _cr,
    "perc": _perc,
}


@lru_cache(maxsize=256)
def drum_sample(name: str, variant: int) -> np.ndarray:
    return DRUMS[name](int(variant)).astype(np.float64)


# --------------------------------------------------------------------------
# pitched voices
# --------------------------------------------------------------------------


def _osc(kind: str, freq: float, t: np.ndarray) -> np.ndarray:
    ph = 2 * np.pi * freq * t
    if kind == "sine":
        return np.sin(ph)
    if kind == "tri":
        return sps.sawtooth(ph, 0.5)
    if kind == "saw":
        return sps.sawtooth(ph)
    if kind == "square":
        return sps.square(ph) * 0.7
    if kind == "supersaw":
        detune = [-0.11, -0.05, 0.0, 0.05, 0.11]
        return sum(sps.sawtooth(ph * (1 + d / 12) + i) for i, d in enumerate(detune)) / 3.0
    raise KeyError(kind)


def _synth(kind: str, freq: float, sustain: float, p: dict) -> np.ndarray:
    attack = _num(p.get("attack"), 0.004)
    release = _num(p.get("release"), 0.06 if kind not in ("pad",) else 0.6)

    if kind in ("superpiano", "piano"):
        t = _t(min(sustain + 1.5, 4.0))
        y = sum(a * np.sin(2 * np.pi * freq * h * t) * np.exp(-t * (1.2 + h * 0.9))
                for h, a in [(1, 1.0), (2, 0.5), (3, 0.28), (4, 0.15), (5, 0.08)])
        env = np.minimum(t / 0.003, 1.0)
        off = t > sustain
        env[off] *= np.exp(-(t[off] - sustain) / 0.25)
        return y * env * 0.7

    if kind == "pluck":
        t = _t(min(sustain + 0.8, 3.0))
        y = sps.sawtooth(2 * np.pi * freq * t) * np.exp(-t / 0.25)
        y = _filt(y, "lowpass", min(freq * 6, 9000))
        return y * np.minimum(t / 0.002, 1.0) * 0.8

    if kind == "bass":
        t = _t(sustain + release)
        y = sps.sawtooth(2 * np.pi * freq * t) * 0.6 + np.sin(2 * np.pi * freq * 0.5 * t) * 0.5
    elif kind == "pad":
        t = _t(sustain + release)
        y = _osc("supersaw", freq, t) * 0.6
        attack = _num(p.get("attack"), 0.25)
    else:
        t = _t(sustain + release)
        y = _osc(kind, freq, t)

    env = np.minimum(t / max(attack, 1e-4), 1.0)
    off = t > sustain
    env[off] *= np.exp(-(t[off] - sustain) / max(release, 1e-3) * 3)
    if kind == "bass" and "cutoff" not in p:
        y = _filt(y, "lowpass", 900)
    if kind == "pad" and "cutoff" not in p:
        y = _filt(y, "lowpass", 2500)
    return y * env * 0.5


SYNTHS = ["sine", "tri", "saw", "square", "supersaw", "superpiano", "piano", "pluck", "bass", "pad"]
SOUND_NAMES = {"drums": list(DRUMS), "synths": SYNTHS}


# --------------------------------------------------------------------------
# effects
# --------------------------------------------------------------------------


def _feedback_delay(x: np.ndarray, d: int, fb: float) -> np.ndarray:
    """Wet output of y[n] = x[n-d] + fb * y[n-d], vectorised in blocks of d."""
    y = np.zeros_like(x)
    y[d:] = x[:-d]
    for k in range(d, len(x), d):
        y[k:k + d] += fb * y[k - d:k][: len(y[k:k + d])]
    return y


def _allpass(x: np.ndarray, d: int, g: float = 0.5) -> np.ndarray:
    y = -g * x
    y[d:] += x[:-d]
    for k in range(d, len(x), d):
        y[k:k + d] += g * y[k - d:k][: len(y[k:k + d])]
    return y


def _reverb(x: np.ndarray, size: float, spread: int = 0) -> np.ndarray:
    fb = 0.72 + 0.26 * min(max(size, 0.0), 1.0)
    combs = [1557, 1617, 1491, 1422, 1277, 1356]
    y = sum(_filt(_feedback_delay(x, c + spread, fb), "lowpass", 5000, 1) for c in combs) / len(combs)
    for a in (556 + spread, 441 + spread, 225):
        y = _allpass(y, a)
    return y


def _circular(process, buf: np.ndarray, settle_s: float) -> np.ndarray:
    """Run an effect as if `buf` looped forever (steady state)."""
    L = len(buf)
    reps = max(2, math.ceil(settle_s * SR / L) + 1)
    out = process(np.tile(buf, reps))
    return out[-L:]


def _add_circular(buf: np.ndarray, start: int, y: np.ndarray, ch: int) -> None:
    L = buf.shape[1]
    start %= L
    pos = 0
    while pos < len(y):
        i = (start + pos) % L
        n = min(L - i, len(y) - pos)
        buf[ch, i:i + n] += y[pos:pos + n]
        pos += n


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


@dataclass
class Render:
    wav_b64: str
    events: list[dict]
    duration: float
    cycles: int
    cps: float
    warnings: list[str] = field(default_factory=list)


def _wav_b64(stereo: np.ndarray) -> str:
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2").T.tobytes()
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    return base64.b64encode(bio.getvalue()).decode()


def query_events(pat: Pattern, cycles: int) -> list:
    evs = [e for e in pat.query(TimeSpan(Fraction(0), Fraction(cycles)))
           if e.whole is not None and e.has_onset()]
    return sorted(evs, key=lambda e: e.whole.begin)


def render(pat: Pattern, cycles: int = 4, cps: float = 0.5) -> Render:
    """Render `cycles` cycles of an eddy control pattern to a looping clip."""
    if not isinstance(pat, Pattern):
        raise TypeError(f"expected an eddy Pattern, got {type(pat).__name__}")
    cycles = int(cycles)
    cps = float(cps)
    L = int(round(cycles / cps * SR))
    dry = np.zeros((2, L))
    sends_room: dict[float, np.ndarray] = {}
    sends_delay: dict[tuple, np.ndarray] = {}
    viz: list[dict] = []
    warnings: list[str] = []
    unknown: set[str] = set()

    for e in query_events(pat, cycles):
        p = flatten_value(e.value)
        name = str(p.get("s", "") or "")
        if not name:
            if "note" in p or "n" in p:
                name = "superpiano"
            else:
                continue
        begin = float(e.whole.begin)
        end = float(e.whole.end)
        dur_s = (end - begin) / cps
        n_raw = p.get("n", 0)

        midi = None
        if name in DRUMS:
            try:
                variant = int(_num(n_raw, 0))
            except (TypeError, ValueError):
                variant = 0
            y = drum_sample(name, variant)
            speed = _num(p.get("speed"), 1.0) * 2 ** (_num(p.get("note"), 0.0) / 12)
            if speed != 1.0 and speed != 0.0:
                n_out = max(1, int(len(y) / abs(speed)))
                y = np.interp(np.linspace(0, len(y) - 1, n_out), np.arange(len(y)), y)
                if speed < 0:
                    y = y[::-1]
            if "legato" in p:
                cut = int(dur_s * _num(p["legato"], 1.0) * SR)
                if cut < len(y):
                    fade = min(256, cut)
                    y = y[:cut].copy()
                    if fade:
                        y[-fade:] *= np.linspace(1, 0, fade)
            label = name if not variant else f"{name}:{variant}"
        elif name in SYNTHS:
            try:
                semis = note_number(p.get("note", 0)) + note_number(n_raw if n_raw is not None else 0)
            except ValueError as ex:
                warnings.append(str(ex))
                continue
            semis += (_num(p.get("octave"), 5) - 5) * 12
            midi = 60 + semis
            freq = 440.0 * 2 ** ((midi - 69) / 12)
            sustain = _num(p.get("sustain"), dur_s * _num(p.get("legato"), 1.0))
            y = _synth(name, freq, max(sustain, 0.01), p)
            label = f"{name} {midi_name(midi)}"
        else:
            unknown.add(name)
            y = drum_sample("perc", 0)
            label = f"{name}?"

        if "cutoff" in p:
            y = _filt(y, "lowpass", _num(p["cutoff"], 20000))
        if "hcutoff" in p:
            y = _filt(y, "highpass", _num(p["hcutoff"], 20))
        if _num(p.get("shape"), 0) > 0:
            k = 1 + min(_num(p["shape"], 0), 0.99) * 12
            y = np.tanh(y * k) / np.tanh(k)
        if "crush" in p:
            q = 2 ** (max(_num(p["crush"], 16), 1) - 1)
            y = np.round(y * q) / q
        if _num(p.get("coarse"), 0) > 1:
            c = int(_num(p["coarse"], 1))
            y = np.repeat(y[::c], c)[: len(y)]

        amp = _num(p.get("gain"), 1.0) ** 1.5 * _num(p.get("amp"), 1.0) * _num(p.get("velocity"), 1.0)
        pan = min(max(_num(p.get("pan"), 0.5), 0.0), 1.0)
        lr = (math.cos(pan * math.pi / 2) * math.sqrt(2) * amp,
              math.sin(pan * math.pi / 2) * math.sqrt(2) * amp)

        start = int(round(begin / cps * SR))
        for ch in (0, 1):
            _add_circular(dry, start, y * lr[ch], ch)

        room = _num(p.get("room"), 0)
        if room > 0:
            size = round(_num(p.get("size"), 0.6), 2)
            bus = sends_room.setdefault(size, np.zeros((2, L)))
            for ch in (0, 1):
                _add_circular(bus, start, y * lr[ch] * room, ch)
        dly = _num(p.get("delay"), 0)
        if dly > 0:
            key = (round(_num(p.get("delaytime"), 0.1875 / cps), 4),
                   round(min(_num(p.get("delayfeedback"), 0.45), 0.95), 3))
            bus = sends_delay.setdefault(key, np.zeros((2, L)))
            for ch in (0, 1):
                _add_circular(bus, start, y * lr[ch] * dly, ch)

        viz.append({
            "begin": begin, "end": end, "s": name, "label": label,
            "midi": midi, "gain": min(amp, 1.5),
        })

    mix = dry.copy()
    for size, bus in sends_room.items():
        for ch in (0, 1):
            mix[ch] += _circular(lambda x: _reverb(x, size, spread=23 * ch), bus[ch], 4.0) * 0.8
    for (dtime, fb), bus in sends_delay.items():
        d = max(1, int(dtime * SR))
        settle = d / SR * math.log(0.001) / math.log(max(fb, 0.01))
        for ch in (0, 1):
            mix[ch] += _circular(lambda x: _feedback_delay(x, d, fb), bus[ch], min(settle, 12.0))

    stereo = np.tanh(mix * MASTER_GAIN)
    if unknown:
        warnings.append(
            f"unknown sound(s): {', '.join(sorted(unknown))} — played as 'perc'. "
            f"Drums: {', '.join(DRUMS)}. Synths: {', '.join(SYNTHS)}."
        )
    return Render(_wav_b64(stereo), viz, L / SR, cycles, cps, warnings)
