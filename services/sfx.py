"""Bruitages du montage, synthétisés par le code (aucun fichier, aucun droit d'auteur).

pop (un élément apparaît), whoosh (une carte glisse), kaching (caisse enregistreuse : le total
change), stamp (tampon), tick (compteur qui défile), type (imprimante du ticket), ding (fin d'un
compteur), hit (impact : citation choc, logo). build_track() pose ces sons aux bons instants sur une piste mono, mixée ensuite sous
la voix (voir render._final_pass).
"""
import array
import math
import random
import wave

SR = 24000
_cache = {}


def _decay(n, tau):
    return [math.exp(-i / (tau * SR)) for i in range(n)]


def _noise(n, seed):
    r = random.Random(seed)
    return [r.uniform(-1.0, 1.0) for _ in range(n)]


def _lowpass(x, cutoff):
    a = math.exp(-2 * math.pi * cutoff / SR)
    out, y = [], 0.0
    for v in x:
        y = (1 - a) * v + a * y
        out.append(y)
    return out


def _highpass(x, cutoff):
    lp = _lowpass(x, cutoff)
    return [v - w for v, w in zip(x, lp)]


def _norm(x, peak):
    m = max(1e-9, max(abs(v) for v in x))
    return [v * peak / m for v in x]


def _pop():
    n = int(0.09 * SR)
    ph, out = 0.0, []
    for i in range(n):
        f = 950 * math.exp(-i / (0.025 * SR)) + 180
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-i / (0.03 * SR)))
    return _norm(out, 0.5)


def _whoosh():
    n = int(0.42 * SR)
    x = _noise(n, 7)
    out, y = [], 0.0
    for i, v in enumerate(x):  # passe-bas dont la fréquence monte puis redescend : souffle qui passe
        p = i / n
        cut = 300 + 2600 * math.sin(math.pi * p) ** 2
        a = math.exp(-2 * math.pi * cut / SR)
        y = (1 - a) * v + a * y
        out.append(y * math.sin(math.pi * p) ** 2)
    return _norm(_highpass(out, 120), 0.45)


def _bell(freqs, n, tau):
    out = [0.0] * n
    for k, f in enumerate(freqs):
        amp = 1.0 / (1 + k * 0.6)
        for i in range(n):
            out[i] += amp * math.sin(2 * math.pi * f * i / SR) * math.exp(-i / (tau / (1 + 0.3 * k) * SR))
    return out


def _kaching():
    n = int(0.95 * SR)
    out = [0.0] * n
    ka = _highpass(_noise(int(0.035 * SR), 3), 1500)  # « ka » : le tiroir mécanique
    for i, v in enumerate(ka):
        out[i] += 0.8 * v * math.exp(-i / (0.01 * SR))
    for start, freqs in ((int(0.05 * SR), (2093, 2637, 3322, 4186)), (int(0.13 * SR), (2349, 2960, 3729, 4699))):
        b = _bell(freqs, n - start, 0.32)
        for i, v in enumerate(b):
            out[start + i] += 0.45 * v
    return _norm(out, 0.5)


def _stamp():
    n = int(0.28 * SR)
    ph, out = 0.0, []
    for i in range(n):
        f = 95 * math.exp(-i / (0.08 * SR)) + 45
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-i / (0.07 * SR)))
    hit = _lowpass(_noise(int(0.03 * SR), 11), 2500)
    for i, v in enumerate(hit):
        out[i] += 0.9 * v * math.exp(-i / (0.008 * SR))
    return _norm(out, 0.6)


def _hit():
    """Impact sourd (citation choc, logo) : grave qui tombe + claquement court."""
    n = int(0.55 * SR)
    ph, out = 0.0, []
    for i in range(n):
        f = 70 * math.exp(-i / (0.12 * SR)) + 38
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-i / (0.16 * SR)))
    snap = _lowpass(_noise(int(0.05 * SR), 13), 3500)
    for i, v in enumerate(snap):
        out[i] += 0.7 * v * math.exp(-i / (0.012 * SR))
    return _norm(out, 0.7)


def _tick():
    n = int(0.012 * SR)
    x = _highpass(_noise(n, 5), 2500)
    return _norm([v * math.exp(-i / (0.002 * SR)) for i, v in enumerate(x)], 0.35)


def _type():
    n = int(0.03 * SR)
    x = _lowpass(_noise(n, 9), 4000)
    out = [v * math.exp(-i / (0.004 * SR)) + 0.3 * math.sin(2 * math.pi * 1300 * i / SR) *
           math.exp(-i / (0.006 * SR)) for i, v in enumerate(x)]
    return _norm(out, 0.3)


def _ding():
    n = int(0.6 * SR)
    return _norm(_bell((1318.5, 1975.5, 2637.0), n, 0.25), 0.4)


SOUNDS = {"pop": _pop, "whoosh": _whoosh, "kaching": _kaching, "stamp": _stamp, "tick": _tick, "hit": _hit,
          "type": _type, "ding": _ding}


def sound(name):
    if name not in _cache:
        _cache[name] = SOUNDS[name]()
    return _cache[name]


def build_track(events, total, dest):
    """events = [(seconde, nom, gain)] → WAV mono 16 bits de `total` secondes (silence ailleurs)."""
    n = int(total * SR) + 1
    acc = {}  # échantillons touchés seulement (la piste est surtout faite de silence)
    for t, name, gain in events:
        if name not in SOUNDS or t < 0:
            continue
        i0 = int(t * SR)
        for j, v in enumerate(sound(name)):
            k = i0 + j
            if k >= n:
                break
            acc[k] = acc.get(k, 0.0) + v * gain
    pcm = array.array("h", bytes(2 * n))
    for k, v in acc.items():
        pcm[k] = max(-32767, min(32767, int(v * 32767)))
    with wave.open(dest, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return dest
