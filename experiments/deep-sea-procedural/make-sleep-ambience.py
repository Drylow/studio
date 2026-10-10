#!/usr/bin/env python3
"""Synthesize a periodic stereo underwater noise bed; no samples or music."""
import argparse
import json
import wave
from pathlib import Path
import numpy as np


def create(seconds, output):
    rate = 48000
    total = round(seconds * rate)
    rng = np.random.default_rng(980115)
    frequencies = np.fft.rfftfreq(total, 1 / rate)
    # Smooth, low-water rumble with little high-frequency hiss, no melody.
    weights = ((1 - np.exp(-(frequencies / 24) ** 4)) /
               (1 + (frequencies / 105) ** 2.5) /
               (1 + (frequencies / 680) ** 6))
    weights[0] = 0
    spectra = []
    for _ in range(2):
        phases = rng.uniform(0, 2 * np.pi, len(frequencies))
        spectra.append(weights * np.exp(1j * phases))
    common = np.fft.irfft(spectra[0], n=total).astype(np.float32)
    independent = np.fft.irfft(spectra[1], n=total).astype(np.float32)
    common /= max(float(np.std(common)), 1e-12)
    independent /= max(float(np.std(independent)), 1e-12)
    # Integer Fourier bins and integer-cycle envelope make the sample stream
    # periodic, including derivatives. There is deliberately no end/start fade.
    phase = np.arange(total, dtype=np.float64) * (2 * np.pi / total)
    tide = (0.94 + 0.045 * np.sin(phase * 3) + 0.015 * np.cos(phase * 7)).astype(np.float32)
    left = (common * 0.9 + independent * 0.1) * tide
    right = (common * 0.9 - independent * 0.1) * tide
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))))
    gain = 0.071 / peak
    pcm = np.empty((total, 2), dtype='<i2')
    pcm[:, 0] = np.rint(left * gain * 32767).astype(np.int16)
    pcm[:, 1] = np.rint(right * gain * 32767).astype(np.int16)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), 'wb') as stream:
        stream.setparams((2, 2, rate, total, 'NONE', 'not compressed'))
        stream.writeframes(pcm.tobytes())
    differences = np.abs(np.diff(pcm.astype(np.int32), axis=0))
    report = {'seconds': total / rate, 'sample_rate': rate, 'channels': 2,
              'peak_dbfs': float(20 * np.log10(np.max(np.abs(pcm.astype(np.int32))) / 32768)),
              'rms_dbfs': float(20 * np.log10(np.sqrt(np.mean((pcm.astype(np.float64) / 32768) ** 2)))),
              'boundary_sample_step': (pcm[0].astype(int) - pcm[-1].astype(int)).tolist(),
              'maximum_adjacent_step': differences.max(axis=0).tolist(),
              'samples_clipped': int(np.sum(np.abs(pcm.astype(np.int32)) >= 32767)),
              'periodic_synthesis': True, 'external_samples': 0}
    output.with_suffix('.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.seconds < 1 or args.seconds > 300:
        parser.error('Use a duration between 1 and 300 seconds.')
    create(args.seconds, args.out)
