"""Kit de bruitages libres de droits, générés par synthèse (whoosh, swish, impact, riser, pop).

Les fichiers sont créés une fois dans assets/sfx/. Un pack perso (assets/sfx/pack/*.wav) peut les
remplacer : un fichier dont le nom commence par « whoosh », « impact »… est utilisé à la place.
"""
import wave
from pathlib import Path

import numpy as np

from . import config

SR = 48000
SFX_DIR = config.ROOT / "assets" / "sfx"
PACK_DIR = SFX_DIR / "pack"
KINDS = ("whoosh", "swish", "impact", "hit", "riser", "pop")


def _write(path: Path, x: np.ndarray) -> None:
    x = x / max(1e-9, np.abs(x).max()) * 0.89
    pcm = (x * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)


def _bandpass_sweep(noise: np.ndarray, f0: float, f1: float, q: float = 1.6) -> np.ndarray:
    """Filtre passe-bande dont la fréquence glisse de f0 à f1 (biquad recalculé par blocs)."""
    out = np.zeros_like(noise)
    n = noise.size
    block = 256
    z1 = z2 = 0.0
    for i in range(0, n, block):
        f = f0 * (f1 / f0) ** (i / n)
        w0 = 2 * np.pi * f / SR
        alpha = np.sin(w0) / (2 * q)
        b0, b2 = alpha, -alpha
        a0, a1, a2 = 1 + alpha, -2 * np.cos(w0), 1 - alpha
        b0, b2, a1, a2 = b0 / a0, b2 / a0, a1 / a0, a2 / a0
        for j in range(i, min(n, i + block)):  # forme directe II transposée
            xj = noise[j]
            y = b0 * xj + z1
            z1 = -a1 * y + z2
            z2 = b2 * xj - a2 * y
            out[j] = y
    return out


def _env(n: int, attack: float, release_pow: float = 2.0) -> np.ndarray:
    t = np.linspace(0, 1, n)
    a = int(n * attack)
    env = np.ones(n)
    env[:a] = np.linspace(0, 1, a) ** 1.5
    env[a:] = (1 - np.linspace(0, 1, n - a)) ** release_pow
    return env * (0.6 + 0.4 * np.sin(np.pi * t))


def generate(force: bool = False) -> dict[str, list[Path]]:
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    made = {}

    def make(name: str, fn):
        p = SFX_DIR / f"{name}.wav"
        if force or not p.exists():
            _write(p, fn())
        made.setdefault(name.rstrip("0123456789_"), []).append(p)

    for k, (dur, f0, f1) in enumerate([(0.55, 300, 4200), (0.45, 2500, 500), (0.65, 200, 3000)], 1):
        make(f"whoosh_{k}", lambda dur=dur, f0=f0, f1=f1: _bandpass_sweep(rng.standard_normal(int(SR * dur)), f0, f1)
             * _env(int(SR * dur), 0.55))
    for k, (dur, f0, f1) in enumerate([(0.22, 1800, 6000), (0.18, 5000, 1500)], 1):
        make(f"swish_{k}", lambda dur=dur, f0=f0, f1=f1: _bandpass_sweep(rng.standard_normal(int(SR * dur)), f0, f1, 2.5)
             * _env(int(SR * dur), 0.35, 3))

    def impact():
        n = int(SR * 1.4)
        t = np.arange(n) / SR
        f = 48 + 70 * np.exp(-t * 18)                       # boom qui descend
        boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
        click = rng.standard_normal(n) * np.exp(-t * 60) * 0.6
        sub = np.sin(2 * np.pi * 38 * t) * np.exp(-t * 2.2) * 0.5
        return boom + click + sub
    make("impact_1", impact)

    def hit():
        n = int(SR * 0.6)
        t = np.arange(n) / SR
        return (np.sin(2 * np.pi * 95 * t) * np.exp(-t * 9) + rng.standard_normal(n) * np.exp(-t * 35) * 0.5)
    make("hit_1", hit)

    def riser():
        n = int(SR * 1.6)
        t = np.linspace(0, 1, n)
        noise = _bandpass_sweep(rng.standard_normal(n), 400, 6000, 3)
        tone = np.sin(2 * np.pi * np.cumsum(200 + 900 * t ** 2) / SR) * 0.3
        return (noise + tone) * t ** 2.2
    make("riser_1", riser)

    def pop():
        n = int(SR * 0.09)
        t = np.arange(n) / SR
        return np.sin(2 * np.pi * (900 - 5000 * t) * t) * np.exp(-t * 55)
    make("pop_1", pop)
    return made


def pick(kind: str, index: int = 0) -> Path:
    """Bruitage d'un type donné ; ceux du pack perso passent en priorité."""
    pack = sorted(PACK_DIR.glob(f"{kind}*.wav")) + sorted(PACK_DIR.glob(f"{kind}*.mp3")) if PACK_DIR.exists() else []
    pool = pack or sorted(SFX_DIR.glob(f"{kind}_*.wav"))
    if not pool:
        generate()
        pool = sorted(SFX_DIR.glob(f"{kind}_*.wav"))
    return pool[index % len(pool)]


def load(path: Path) -> np.ndarray:
    """Charge un son en float32 mono 48 kHz (via ffmpeg pour tous les formats)."""
    import subprocess
    raw = subprocess.run([config.get("FFMPEG"), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()
