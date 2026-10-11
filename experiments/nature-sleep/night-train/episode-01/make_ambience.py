#!/usr/bin/env python3
"""Compose two original, periodic train-sleep stems without external audio.

The entire signal is built on a 240-second torus: FFT noise, oscillators,
envelopes and stereophonic motion all return to their initial state.
The encoder receives float PCM and stores lossless 16-bit/24 kHz FLAC.
No two-hour intermediate file is needed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from scipy.fft import irfft, rfftfreq


RATE = 24000
DURATION = 240
SAMPLES = RATE * DURATION
SEED = 119271
TARGET_LUFS = -24.0


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, capture_output=True, text=True)


def cyclic_noise(rng: np.random.Generator, kind: str) -> np.ndarray:
    """A random Fourier field, exactly periodic, shaped for its physical role."""
    f = rfftfreq(SAMPLES, 1 / RATE).astype(np.float32)
    z = (rng.standard_normal(f.size, dtype=np.float32)
         + 1j * rng.standard_normal(f.size, dtype=np.float32)).astype(np.complex64)
    safe = np.maximum(f, 1.0)
    if kind == "rain":
        # Rain behind closed glass: softened high end; no hiss at 10 kHz.
        shape = (1 / safe**0.26) * (1 - np.exp(-(f / 150)**3))
        shape *= np.exp(-(f / 3250)**2.7)
        shape *= 0.75 + 0.25 * np.exp(-((f - 1250) / 1100)**2)
    elif kind == "wheels":
        # A broad, damped wash. No sharp wheel clack or narrow pure-tone whine.
        shape = np.exp(-((f - 75) / 66)**2)
        shape *= 1 - np.exp(-(f / 33)**4)
        shape += 0.16 * np.exp(-((f - 245) / 135)**2)
        shape *= np.exp(-(f / 570)**4)
    elif kind == "cabin":
        shape = (1 / safe**0.50) * (1 - np.exp(-(f / 90)**3))
        shape *= np.exp(-(f / 1600)**2.0)
    elif kind == "pad_air":
        shape = (1 / safe**0.7) * (1 - np.exp(-(f / 240)**3))
        shape *= np.exp(-(f / 1100)**2.5)
    else:
        raise ValueError(kind)
    z *= shape.astype(np.float32)
    z[0] = 0
    z[-1] = 0
    x = irfft(z, n=SAMPLES, workers=2).astype(np.float32)
    x /= math.sqrt(float(np.mean(x.astype(np.float64)**2)))
    return x


def shared_stereo(rng: np.random.Generator, kind: str, width: float) -> np.ndarray:
    middle = cyclic_noise(rng, kind)
    side = cyclic_noise(rng, kind)
    return np.column_stack((middle + width * side, middle - width * side)).astype(np.float32)


def envelope(turns: np.ndarray, phase: float, width: float = 2.4) -> np.ndarray:
    # Circular Gaussian-like raised envelope: no attacks or discontinuities.
    return np.exp(width * (np.cos(turns - phase) - 1)).astype(np.float32)


def make_train(rng: np.random.Generator, t: np.ndarray) -> np.ndarray:
    cycle = t * np.float32(2 * np.pi / DURATION)
    rain = shared_stereo(rng, "rain", 0.31)
    # Very slow variation, not the cyclical pump of a compressor.
    weather = 0.92 + 0.045 * np.sin(cycle + 1.1) + 0.035 * np.sin(3 * cycle + 0.2)
    rain *= weather[:, None]
    wheels = shared_stereo(rng, "wheels", 0.11)
    wheels *= (0.30 + 0.015 * np.sin(2 * cycle + 0.8))[:, None]
    cabin = shared_stereo(rng, "cabin", 0.24)
    cabin *= (0.10 + 0.008 * np.cos(5 * cycle))[:, None]
    # Soft patches of denser drops, spatially on the right-hand window.
    droplets = shared_stereo(rng, "rain", 0.18)
    wavering = (0.5 + 0.5 * np.sin(19 * cycle + 2.0))**4
    droplets *= (0.025 * wavering)[:, None]
    droplets[:, 0] *= 0.56
    out = rain + wheels + cabin + droplets
    return out.astype(np.float32)


def make_music(rng: np.random.Generator, t: np.ndarray) -> np.ndarray:
    """An original four-minute suspended pad, no melody or percussion."""
    cycle = t.astype(np.float64) * (2 * np.pi / DURATION)
    out = np.zeros((SAMPLES, 2), dtype=np.float32)
    # D6/add9, B minor 7/add11, Gmaj7/add9, suspended A: overlapping clouds.
    chords = [
        [50, 57, 62, 66, 69, 71, 76],
        [47, 54, 59, 62, 66, 69, 76],
        [43, 55, 59, 62, 66, 69, 74],
        [45, 57, 62, 64, 69, 71, 74],
    ]
    for chord_index, notes in enumerate(chords):
        swell = envelope(cycle, chord_index * np.pi / 2)
        for note_index, midi in enumerate(notes):
            hz = 440 * 2 ** ((midi - 69) / 12)
            # Frequency quantisation is below 0.0042 Hz; makes a true loop.
            fundamental_cycles = round(hz * DURATION)
            phase = rng.uniform(0, 2 * np.pi)
            spread = (-0.38 + 0.76 * note_index / (len(notes) - 1))
            gain_l = math.sqrt((1 - spread) / 2)
            gain_r = math.sqrt((1 + spread) / 2)
            # A muted, breathy timbre, gently modulated without a tremolo beat.
            voice = np.zeros(SAMPLES, dtype=np.float32)
            for harmonic, amplitude in [(1, 1.0), (2, 0.20), (3, 0.042)]:
                partial_cycles = fundamental_cycles * harmonic
                drift = 0.10 * np.sin(2 * cycle + note_index + chord_index)
                osc = np.sin(partial_cycles * cycle + phase + drift)
                voice += (amplitude * osc).astype(np.float32)
            weight = 0.12 if note_index == 0 else 0.065
            voice *= swell * weight
            out[:, 0] += voice * gain_l
            out[:, 1] += voice * gain_r
    air = shared_stereo(rng, "pad_air", 0.32)
    out += air * 0.005
    return out


def loudness(path: Path) -> dict:
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
             "-af", "loudnorm=I=-24:LRA=11:TP=-3:print_format=json",
             "-f", "null", "-"])
    return json.loads(p.stderr[p.stderr.rfind("{"):p.stderr.rfind("}") + 1])


def encode(path: Path, pcm: np.ndarray) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
           "-f", "f32le", "-ar", str(RATE), "-ac", "2", "-i", "pipe:0",
           "-c:a", "flac", "-sample_fmt", "s16", "-compression_level", "8", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for start in range(0, SAMPLES, RATE * 10):
            proc.stdin.write(pcm[start:start + RATE * 10].astype("<f4").tobytes())
        proc.stdin.close()
    except Exception:
        proc.kill()
        raise
    if proc.wait() != 0:
        raise RuntimeError(f"Could not encode {path}")


def cyclic_metrics(pcm: np.ndarray) -> dict:
    # Last-to-first derivative must be comparable to ordinary adjacent samples.
    ordinary = np.diff(pcm, axis=0)
    delta = pcm[0] - pcm[-1]
    typical99 = np.quantile(np.abs(ordinary), 0.99, axis=0)
    return {
        "seam_delta_per_channel": delta.tolist(),
        "ordinary_adjacent_delta_p99": typical99.tolist(),
        "seam_delta_divided_by_p99": (np.abs(delta) / typical99).tolist(),
        "periodicity_method": "Fourier noise and integer-cycle envelopes/oscillators",
        "boundary_sample_is_not_duplicated": True,
    }


def spectrum(pcm: np.ndarray) -> dict:
    from scipy.signal import welch
    f, power = welch(pcm.mean(axis=1), fs=RATE, nperseg=32768)
    total = float(np.sum(power))
    return {
        f"power_fraction_{lo}_{hi}_hz": float(np.sum(power[(f >= lo) & (f < hi)]) / total)
        for lo, hi in [(0, 30), (30, 200), (200, 2000), (2000, 6000), (6000, 12000)]
    }


def produce(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    if any((out / name).exists() for name in ["ambience.flac", "music.flac", "receipt.json"]):
        raise SystemExit("Refusing to overwrite an existing ambience delivery.")
    # Float64 time is needed for the oscillator phase to remain smooth at 240s.
    t = np.arange(SAMPLES, dtype=np.float64) / RATE
    receipt = {
        "provenance": "Original procedural synthesis; no third-party audio, samples or musical source",
        "duration_seconds": DURATION,
        "sample_rate": RATE,
        "channels": 2,
        "pcm_bits": 16,
        "seed": SEED,
        "target_integrated_lufs": TARGET_LUFS,
        "exact_repetitions_for_two_hours": 30,
        "human_or_model_listening_completed": False,
        "stems": {},
    }
    for index, (name, composer) in enumerate([("ambience", make_train), ("music", make_music)]):
        print(f"Composing {name}...", flush=True)
        pcm = composer(np.random.default_rng(SEED + index), t)
        pcm -= pcm.mean(axis=0)
        # A conservative first encode; final processing uses a constant gain.
        pcm *= 0.15 / max(float(np.max(np.abs(pcm))), 1e-8)
        scratch = out / f".{name}-measure.flac"
        encode(scratch, pcm)
        before = loudness(scratch)
        gain_db = TARGET_LUFS - float(before["input_i"])
        gain_db = min(gain_db, -3.0 - float(before["input_tp"]))
        pcm *= 10 ** (gain_db / 20)
        path = out / f"{name}.flac"
        encode(path, pcm)
        scratch.unlink()
        measurement = loudness(path)
        # Validate losslessly decoded samples, including the actual boundary.
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                                  "-f", "f32le", "-"], check=True, capture_output=True).stdout
        decoded_pcm = np.frombuffer(decoded, dtype="<f4").reshape(-1, 2)
        assert decoded_pcm.shape == (SAMPLES, 2)
        seam = cyclic_metrics(decoded_pcm)
        assert max(seam["seam_delta_divided_by_p99"]) < 2.0
        assert float(measurement["input_tp"]) <= -3.0
        details = {
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decoded_samples_per_channel": decoded_pcm.shape[0],
            "integrated_lufs": float(measurement["input_i"]),
            "true_peak_dbtp": float(measurement["input_tp"]),
            "loudness_range_lu": float(measurement["input_lra"]),
            "static_gain_db_after_first_encode": gain_db,
            "rms_dbfs": [float(20 * np.log10(np.sqrt(np.mean(decoded_pcm[:, ch].astype(np.float64)**2))))
                          for ch in [0, 1]],
            "seam": seam,
            "spectrum": spectrum(decoded_pcm),
        }
        receipt["stems"][name] = details
        print(json.dumps({"stem": name, "lufs": details["integrated_lufs"],
                          "true_peak_dbtp": details["true_peak_dbtp"],
                          "bytes": details["bytes"]}), flush=True)
        del pcm, decoded_pcm, decoded
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    # A private review excerpt across the actual 240s boundary, 20s either side.
    for name in ["ambience", "music"]:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
             "-stream_loop", "1", "-i", str(out / f"{name}.flac"),
             "-ss", "220", "-t", "40", "-c:a", "flac", str(out / f"{name}-seam-preview.flac")])
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
         "-i", str(out / "ambience-seam-preview.flac"),
         "-i", str(out / "music-seam-preview.flac"),
         "-filter_complex", "[0:a]volume=-15dB[a];[1:a]volume=-18dB[m];[a][m]amix=inputs=2:normalize=0[out]",
         "-map", "[out]", "-c:a", "flac", str(out / "quiet-bed-seam-preview.flac")])
    size = sum(p.stat().st_size for p in out.iterdir() if p.is_file())
    assert size < 100_000_000, size
    print(f"Done: {size} bytes including review previews.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    produce(args.out.resolve())
