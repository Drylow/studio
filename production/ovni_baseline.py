"""Measure the existing studio renderer on the same approved OVNI test inputs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from ovni_smoke import save, selected_shots

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('timeline', 'approval', 'audio', 'ffmpeg', 'output'):
        parser.add_argument('--' + field, required=True)
    parser.add_argument('--seconds', type=float, default=30)
    args = parser.parse_args()
    output = Path(args.output)
    assert not output.exists(), 'Baseline needs an empty, uncached directory'
    output.mkdir(parents=True)
    shots = selected_shots(json.loads(Path(args.timeline).read_text(encoding='utf-8')),
                           json.loads(Path(args.approval).read_text(encoding='utf-8')), args.seconds)
    started = time.perf_counter()
    audio = output / 'narration.mp3'
    subprocess.run([args.ffmpeg, '-v', 'error', '-n', '-i', args.audio, '-t', str(args.seconds),
                    '-c:a', 'libmp3lame', '-q:a', '2', str(audio)], check=True)
    audio_seconds = time.perf_counter() - started
    started = time.perf_counter()
    result = render.render_video(str(output / 'render'), shots, str(audio),
                                 str(output / 'CPU-TECHNICAL-TEST-NOT-PUBLISHABLE.mp4'),
                                 width=1920, height=1080, fps=30, motion_strength=0.025,
                                 transition='none', normalize=False, quality='high',
                                 captions={'mode': 'none'}, tail=0,
                                 progress=lambda p, msg: print(f'{p:.0%} {msg}', flush=True))
    elapsed = time.perf_counter() - started
    save(output / 'benchmark.json', {'phase': 'technical-test-NOT-complete-episode',
                                    'renderer': 'Existing services.render with fresh cache',
                                    'duration': args.seconds, 'images': len(shots),
                                    'audio_prepare_seconds': audio_seconds,
                                    'render_seconds': elapsed, 'result': result,
                                    'comparison_caveat': 'Same inputs, cadence, size and zoom strength; '
                                    'studio easing and interpolation differ. CPU uses CRF 18, OVNI uses '
                                    '8 Mbps/P3. Not identical quality settings or a universal speed claim.',
                                    'publication_ready': False})
    print(f'Studio baseline: {elapsed:.3f}s plus {audio_seconds:.3f}s audio preparation', flush=True)


if __name__ == '__main__':
    main()
