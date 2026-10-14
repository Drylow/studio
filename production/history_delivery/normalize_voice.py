"""Measure and normalize one official voice without changing its sample clock."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

import av
import imageio_ffmpeg


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def decoded(path):
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        count = sum(frame.samples for frame in container.decode(audio=0))
        return {'samples': count, 'rate': stream.codec_context.sample_rate,
                'layout': stream.codec_context.layout.name}


def measure(ffmpeg, path):
    result = subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-xerror', '-i', str(path),
        '-vn', '-af', 'loudnorm=I=-17:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
        check=True, capture_output=True, text=True)
    return json.loads(re.findall(r'\{\s*"input_i".*?\}', result.stderr, re.S)[-1])


def normalize(source, target, proof_path):
    source, target, proof_path = map(lambda path: Path(path).resolve(), (source, target, proof_path))
    if proof_path.exists():
        proof = json.loads(proof_path.read_text())
        if proof['source_sha256'] != digest(source) or proof['derived_sha256'] != digest(target):
            raise ValueError('Existing normalization proof no longer matches its files')
        return proof
    if target.exists():
        raise ValueError('Unproved output exists; preserve it for inspection')
    original_decode = decoded(source)
    if original_decode['rate'] != 44100 or original_decode['layout'] != 'mono':
        raise ValueError('This history finishing profile requires a 44100 Hz mono official voice')
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    original_levels = measure(ffmpeg, source)
    chain = ('loudnorm=I=-17:TP=-1.5:LRA=11:linear=true:print_format=json:'
        f"measured_I={original_levels['input_i']}:measured_TP={original_levels['input_tp']}:"
        f"measured_LRA={original_levels['input_lra']}:measured_thresh={original_levels['input_thresh']}:"
        f"offset={original_levels['target_offset']}")
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-n', '-xerror', '-i', str(source),
        '-af', chain, '-ac', '1', '-ar', '44100', '-c:a', 'flac', str(target)],
        capture_output=True, check=True)
    final_levels, derived_decode = measure(ffmpeg, target), decoded(target)
    if original_decode != derived_decode:
        raise ValueError('Normalization changed sample count, rate or channel layout; no proof released')
    if not (-19 < float(final_levels['input_i']) < -15 and float(final_levels['input_tp']) < -.3):
        raise ValueError('Normalized output levels failed; inspect without overwriting')
    proof = {'source': str(source), 'source_sha256': digest(source), 'derived': str(target),
        'derived_sha256': digest(target), 'original_levels': original_levels,
        'final_levels': final_levels, 'source_decode': original_decode,
        'derived_decode': derived_decode, 'drift_samples': 0, 'drift_ms': 0,
        'operation': 'Two-pass level-only normalization. Sample count/rate/layout preserved; '
                     'amplitudes changed. No new speech, timing edit or visual rendering.'}
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = proof_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(proof, indent=2) + '\n')
    temporary.replace(proof_path)
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--proof', type=Path, required=True)
    args = parser.parse_args()
    proof = normalize(args.source, args.output, args.proof)
    print(json.dumps({'state': 'measured_level_only_normalization_complete',
        'sha256': proof['derived_sha256'], 'drift_samples': proof['drift_samples'],
        'lufs': proof['final_levels']['input_i'], 'proof': str(args.proof)}))


if __name__ == '__main__':
    main()
