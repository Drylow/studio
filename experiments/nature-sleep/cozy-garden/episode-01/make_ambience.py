#!/usr/bin/env python3
"""Make an original periodic garden soundscape and reuse our existing music.

No external recordings, API calls or purchases. The ambience is newly
synthesised. The original pad is copied byte-for-byte, never regenerated here.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess

import numpy as np
from scipy.fft import irfft, rfftfreq


ROOT = Path(__file__).resolve().parents[4]
ENGINE_PATH = ROOT / "experiments/nature-sleep/night-train/episode-01/make_ambience.py"
spec = importlib.util.spec_from_file_location("original_periodic_audio_tools", ENGINE_PATH)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

RATE = 24000
DURATION = 240
SAMPLES = RATE * DURATION
SEED = 418521
MUSIC_SHA256 = "64e87d3af1d0bde0257a7d8e73e09e2ed46268d26dffb0f983c9aa755593df87"
DEFAULT_MUSIC = ROOT / "output/nature-sleep/night-train-production/ambience/music.flac"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field(rng: np.random.Generator, kind: str) -> np.ndarray:
    """Continuous circular noise, with separate leaf/wood/water spectra."""
    f = rfftfreq(SAMPLES, 1 / RATE).astype(np.float32)
    z = (rng.standard_normal(f.size, dtype=np.float32)
         + 1j * rng.standard_normal(f.size, dtype=np.float32)).astype(np.complex64)
    safe = np.maximum(f, 1.0)
    if kind == "leaves":
        shape = safe**-0.20 * (1 - np.exp(-(f / 255)**4))
        shape *= np.exp(-(f / 3850)**2.8)
    elif kind == "pergola":
        shape = safe**-0.40 * (1 - np.exp(-(f / 145)**4))
        shape *= np.exp(-(f / 1850)**2.1)
        shape *= 0.65 + 0.35 * np.exp(-((f - 730) / 610)**2)
    elif kind == "water":
        shape = (0.50 * np.exp(-((f - 540) / 390)**2)
                 + 0.33 * np.exp(-((f - 1380) / 710)**2)
                 + 0.08 * np.exp(-((f - 2550) / 700)**2))
        shape *= 1 - np.exp(-(f / 190)**4)
        shape *= np.exp(-(f / 4300)**3)
    elif kind == "ripples":
        shape = safe**-0.28 * (1 - np.exp(-(f / 310)**4))
        shape *= np.exp(-(f / 1300)**2.2)
    else:
        raise ValueError(kind)
    z *= shape.astype(np.float32)
    z[0] = z[-1] = 0
    pcm = irfft(z, n=SAMPLES, workers=2).astype(np.float32)
    pcm /= math.sqrt(float(np.mean(pcm.astype(np.float64)**2)))
    return pcm


def stereo_field(rng: np.random.Generator, kind: str, width: float) -> np.ndarray:
    center, side = field(rng, kind), field(rng, kind)
    return np.column_stack((center + width * side, center - width * side))


def compose() -> np.ndarray:
    rng = np.random.default_rng(SEED)
    angle = np.arange(SAMPLES, dtype=np.float64) * (2 * np.pi / SAMPLES)
    # More distant rain on foliage; no sudden gusts or prominent isolated drops.
    leaves = stereo_field(rng, "leaves", 0.32)
    leaves *= (0.68 + 0.022 * np.sin(angle + 1.2)
               + 0.018 * np.sin(3 * angle + 0.6))[:, None]
    # Soft shelter overhead, not a metal-roof tap or a resonant impact.
    pergola = stereo_field(rng, "pergola", 0.18)
    pergola *= (0.40 + 0.013 * np.cos(2 * angle + 0.7))[:, None]
    # The small stream is on the right of the frame; keep its movement subtle.
    water = stereo_field(rng, "water", 0.15)
    water *= (0.175 + 0.009 * np.sin(11 * angle + 2.1)
              + 0.006 * np.sin(29 * angle + 0.3))[:, None]
    water[:, 0] *= 0.72
    ripples = stereo_field(rng, "ripples", 0.20)
    ripples *= (0.046 + 0.004 * np.cos(17 * angle - 0.8))[:, None]
    ripples[:, 0] *= 0.80
    pcm = (leaves + pergola + water + ripples).astype(np.float32)
    pcm -= pcm.mean(axis=0)
    return pcm


def inspect(path: Path, provenance: str) -> dict:
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels,bits_per_raw_sample,duration",
        "-of", "json", str(path)]))['streams'][0]
    assert probe['codec_name'] == 'flac'
    assert int(probe['sample_rate']) == RATE and probe['channels'] == 2
    assert int(probe['bits_per_raw_sample']) == 16
    assert float(probe['duration']) == DURATION
    level = engine.loudness(path)
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                                   "-f", "f32le", "-"])
    pcm = np.frombuffer(raw, dtype='<f4').reshape(-1, 2)
    assert pcm.shape == (SAMPLES, 2)
    seam = engine.cyclic_metrics(pcm)
    assert max(seam['seam_delta_divided_by_p99']) < 2
    assert abs(float(level['input_i']) + 24) <= 0.05
    assert float(level['input_tp']) <= -3
    result = {
        'file': path.name, 'provenance': provenance, 'sha256': digest(path),
        'bytes': path.stat().st_size, 'duration_seconds': DURATION,
        'decoded_samples_per_channel': SAMPLES,
        'integrated_lufs': float(level['input_i']),
        'true_peak_dbtp': float(level['input_tp']),
        'loudness_range_lu': float(level['input_lra']),
        'rms_dbfs': [float(20 * np.log10(np.sqrt(np.mean(pcm[:, c].astype(np.float64)**2)))) for c in [0, 1]],
        'seam': seam, 'spectrum': engine.spectrum(pcm),
        'full_lossless_decode': True,
    }
    print(json.dumps({k: result[k] for k in ['file', 'integrated_lufs', 'true_peak_dbtp', 'bytes']}), flush=True)
    return result


def produce(out: Path, music: Path) -> None:
    if not music.is_file() or digest(music) != MUSIC_SHA256:
        raise SystemExit('The existing original music is missing or its checksum differs; not regenerating it.')
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise SystemExit('Output directory must be empty; refusing to overwrite a delivery.')
    print('Synthesising garden foliage, pergola rain and small flowing water...', flush=True)
    pcm = compose()
    pcm *= 0.15 / float(np.max(np.abs(pcm)))
    scratch = out / '.measure.flac'
    engine.encode(scratch, pcm)
    before = engine.loudness(scratch)
    gain = min(-24 - float(before['input_i']), -3 - float(before['input_tp']))
    pcm *= 10 ** (gain / 20)
    engine.encode(out / 'ambience.flac', pcm)
    scratch.unlink()
    del pcm
    shutil.copyfile(music, out / 'music.flac')
    assert digest(out / 'music.flac') == MUSIC_SHA256
    receipt = {
        'duration_seconds': DURATION, 'sample_rate': RATE, 'channels': 2, 'pcm_bits': 16,
        'seed': SEED, 'target_integrated_lufs': -24, 'exact_repetitions_for_two_hours': 30,
        'audio_sources': 'New original procedural garden soundscape; byte-identical reuse of our original pad.',
        'excluded_sounds': ['train rumble', 'rail clacks', 'thunder', 'bird calls', 'sudden impacts'],
        'human_or_model_listening_completed': False,
        'source_code_sha256': digest(Path(__file__)),
        'stems': {
            'ambience': inspect(out / 'ambience.flac', 'Original synthesis of rain on leaves/wood and soft moving water.'),
            'music': inspect(out / 'music.flac', 'Byte-for-byte copy of the original in-house pad; no regeneration.'),
        },
    }
    receipt['stems']['ambience']['static_gain_db_after_first_encode'] = gain
    receipt['stems']['music']['source_relative_path'] = str(music.relative_to(ROOT)) if music.is_relative_to(ROOT) else music.name
    for name in ['ambience', 'music']:
        engine.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
                    '-stream_loop', '1', '-i', str(out / f'{name}.flac'), '-ss', '220', '-t', '40',
                    '-c:a', 'flac', str(out / f'{name}-seam-preview.flac')])
    engine.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
                '-i', str(out / 'ambience-seam-preview.flac'), '-i', str(out / 'music-seam-preview.flac'),
                '-filter_complex', '[0:a]volume=-15dB[a];[1:a]volume=-20dB[m];[a][m]amix=inputs=2:normalize=0[out]',
                '-map', '[out]', '-c:a', 'flac', str(out / 'quiet-bed-seam-preview.flac')])
    receipt['review_excerpt_seconds'] = 40
    receipt['suggested_mix_gain_db'] = {'ambience': -15, 'music': -20}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    total = sum(x.stat().st_size for x in out.iterdir() if x.is_file())
    assert total < 50_000_000
    print(f'Complete: {total} bytes, stems and seam previews.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--music', type=Path, default=DEFAULT_MUSIC)
    args = parser.parse_args()
    produce(args.out.resolve(), args.music.resolve())
