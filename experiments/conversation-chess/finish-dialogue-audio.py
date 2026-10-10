"""Raise source-scene audio after a native export, preserving guide and SFX levels."""
import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path


def picture_hash(file):
    return subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(file), '-map', '0:v:0',
        '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-'
    ]).decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--gain-db', type=float, required=True)
    args = parser.parse_args()
    if not math.isfinite(args.gain_db) or not 0 <= args.gain_db <= 12:
        parser.error('Use a reviewed gain between 0 and 12 dB.')
    base = (args.input or args.bundle / 'video.mp4').resolve()
    dest = args.out.resolve()
    if dest.exists() or dest == base:
        parser.error('Preserve the previous export: choose a new output filename.')
    manifest = json.loads((args.bundle / 'project-manifest.json').read_text(encoding='utf-8'))
    fps = float(manifest['fps'])
    ranges = [(s['start_frame'] / fps, s['end_frame'] / fps)
              for s in manifest['segments'] if s['kind'] == 'source']
    if not ranges:
        parser.error('The native manifest contains no source scenes.')
    mask = '+'.join(f'between(t,{a:.9f},{b:.9f})' for a, b in ranges)
    audio_filter = f"volume='1+(pow(10,{args.gain_db}/20)-1)*min(1,{mask})':eval=frame"
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-n', '-v', 'warning', '-i', str(base), '-map', '0:v:0',
                    '-map', '0:a:0', '-c:v', 'copy', '-af', audio_filter,
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                    '-movflags', '+faststart', str(dest)], check=True)
    original_picture_hash = picture_hash(base)
    if picture_hash(dest) != original_picture_hash:
        raise RuntimeError('The video stream changed during audio finishing.')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(dest), '-map',
                    '0:v:0', '-map', '0:a:0', '-f', 'null', '-'],
                   stdout=subprocess.DEVNULL, check=True)
    measure = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(dest), '-vn',
                              '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             text=True, check=True).stderr
    summary = measure.rsplit('Summary:', 1)[-1]
    peak_match = re.search(r'Peak:\s*([-\d.]+) dBFS', summary)
    loudness_match = re.search(r'I:\s*([-\d.]+) LUFS', summary)
    if not peak_match or not loudness_match:
        raise RuntimeError('Audio measurements are unavailable.')
    peak = float(peak_match.group(1))
    if peak > -1:
        raise RuntimeError(f'True peak {peak} dBFS exceeds -1 dBFS; use a lower gain and a new filename.')
    receipt = dict(filename=dest.name, sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                   bytes=dest.stat().st_size, source_audio_gain_db=args.gain_db,
                   source_output_ranges=ranges, intro_analysis_outro_audio_gain_db=0,
                   picture_stream_unchanged=True, picture_stream_sha256=original_picture_hash,
                   filter=audio_filter, full_decode_passed=True,
                   true_peak_dbfs=peak, integrated_loudness_lufs=float(loudness_match.group(1)))
    dest.with_suffix('.audio.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
