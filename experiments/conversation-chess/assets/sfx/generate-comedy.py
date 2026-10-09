#!/usr/bin/env python3
"""Reproduce three original short cartoon cues; no imported audio or melodies.

The script and its generated audio are dedicated under CC0 1.0 Universal.
All sound is computed from deterministic oscillators and filtered noise.
"""
from pathlib import Path
import hashlib
import json
import math
import random
import struct
import wave

ROOT = Path(__file__).resolve().parent
RATE = 48_000


def oscillator(frequencies):
    phase = 0.0
    out = []
    for frequency in frequencies:
        phase += 2 * math.pi * frequency / RATE
        out.append(math.sin(phase))
    return out


def save(name, values, peak_db, description):
    # Finite smooth edges keep the first and last PCM sample exactly zero.
    attack = int(.004 * RATE)
    release = int(.035 * RATE)
    for i in range(len(values)):
        edge = min(1, i / attack, (len(values) - 1 - i) / release)
        values[i] *= .5 - .5 * math.cos(math.pi * max(0, edge))
    amplitude = 10 ** (peak_db / 20) / max(abs(v) for v in values)
    pcm = b''.join(struct.pack('<h', round(v * amplitude * 32767)) for v in values)
    path = ROOT / name
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        output.writeframes(pcm)
    return {'file': name, 'source_group': 'edgerunners_original_cc0',
            'processing': description + '; 4 ms onset, 35 ms ending fades; mono PCM16 at 48 kHz',
            'license': 'CC0 1.0 Universal', 'duration_seconds': len(values) / RATE,
            'peak_dbfs': peak_db, 'sample_rate': RATE, 'channels': 1,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def impact():
    # A short low thump with a noisy burst: the familiar comic impact idiom,
    # without sampling or reproducing a named meme recording.
    count = round(.78 * RATE)
    times = [i / RATE for i in range(count)]
    bass = oscillator([43 + 75 * math.exp(-t * 19) for t in times])
    ring = oscillator([117 + 42 * math.exp(-t * 13) for t in times])
    rng = random.Random(14912)
    low_noise = 0.0
    signal = []
    for t, low, high in zip(times, bass, ring):
        noise = rng.uniform(-1, 1)
        cutoff = 550 + 2400 * math.exp(-t * 24)
        alpha = 1 - math.exp(-2 * math.pi * cutoff / RATE)
        low_noise += alpha * (noise - low_noise)
        signal.append(.70 * low * math.exp(-t * 6.7)
                      + .16 * high * math.exp(-t * 11)
                      + .39 * low_noise * math.exp(-t * 17))
    return save('original-comic-impact.wav', signal, -9,
                'Original oscillator bass sweep 118→43 Hz plus decaying harmonic and seeded filtered-noise burst (seed 14912)')


def pop():
    count = round(.18 * RATE)
    times = [i / RATE for i in range(count)]
    tone = oscillator([320 + 900 * math.exp(-t * 31) for t in times])
    body = oscillator([170 + 230 * math.exp(-t * 32) for t in times])
    signal = [(.85 * a + .15 * b) * math.exp(-t * 26) for t, a, b in zip(times, tone, body)]
    return save('original-soft-pop.wav', signal, -16,
                'Original descending rounded bubble oscillator 1220→320 Hz with quiet lower body; exponential decay')


def twinkle():
    count = round(.62 * RATE)
    signal = [0.0] * count
    # An original three-note accent, never a loop or under-dialogue music bed.
    for start, frequency in [(0.0, 880), (.085, 1174.659), (.17, 1396.913)]:
        onset = round(start * RATE)
        for i in range(onset, count):
            t = (i - onset) / RATE
            envelope = (1 - math.exp(-t * 650)) * math.exp(-t * 9)
            signal[i] += envelope * (math.sin(2 * math.pi * frequency * t)
                                     + .14 * math.sin(2 * math.pi * frequency * 2.007 * t))
    return save('original-rising-twinkle.wav', signal, -15,
                'Original three-note bell-like oscillator accent A5→D6→F6 with decaying envelopes and faint inharmonic partial')


if __name__ == '__main__':
    measurements = [impact(), pop(), twinkle()]
    (ROOT / 'original-comedy-provenance.json').write_text(json.dumps({
        'license': 'CC0 1.0 Universal', 'author': 'Edgerunners Studio',
        'created': '2026-10-09', 'source': 'generate-comedy.py', 'assets': measurements,
        'scope': 'Original local sound-design cues; no reference-channel audio sampled or copied.'
    }, indent=2) + '\n')
    print(json.dumps(measurements, indent=2))
