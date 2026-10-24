"""Render directed still-image slideshows without changing narration clocks.

The caller supplies reviewed image paths and exact shot boundaries. This module
does no authoring or generation. Dissolves straddle existing cut boundaries;
they never subtract time from the narration. Run only on the production host.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageOps


def shot_frames(scenes, duration, fps):
    """Round cumulative boundaries, avoiding one rounding error per shot."""
    cursor = 0
    counts = []
    previous_end = 0.0
    for index, scene in enumerate(scenes):
        if abs(float(scene['start']) - previous_end) > .05:
            raise ValueError('Shots must be contiguous')
        end = duration if index == len(scenes) - 1 else float(scene['end'])
        boundary = round(end * fps)
        if boundary <= cursor:
            raise ValueError('Every shot needs at least one frame')
        counts.append(boundary - cursor)
        cursor = boundary
        previous_end = float(scene['end'])
    if not counts or abs(previous_end - duration) > .05:
        raise ValueError('Shots must cover the actual narration')
    return counts


def dissolve_widths(counts, fps, seconds):
    requested = max(0, round(seconds * fps))
    # A centered dissolve uses only half its width in each adjacent shot.
    # Leave at least one hold frame, including between two long dissolves.
    return [min(requested, max(0, counts[i] - 1), max(0, counts[i + 1] - 1))
            for i in range(len(counts) - 1)]


def render(job):
    width, height, fps = (int(job.get(k, default))
                          for k, default in [('width', 1920), ('height', 1080), ('fps', 24)])
    if min(width, height, fps) <= 0:
        raise ValueError('Invalid output size or frame rate')
    duration = float(job['duration'])
    scenes = job['scenes']
    counts = shot_frames(scenes, duration, fps)
    transitions = dissolve_widths(counts, fps, float(job.get('transition_seconds', .25)))
    if job.get('strict_transition_seconds') and any(
            n != round(float(job.get('transition_seconds', .25)) * fps) for n in transitions):
        raise ValueError('A shot is too short for the requested dissolve')
    intro_frames = min(sum(counts), max(0, round(float(job.get('intro_fade_seconds', 0)) * fps)))
    outro_frames = min(sum(counts), max(0, round(float(job.get('outro_fade_seconds', 0)) * fps)))
    filters = [f'fps={fps}', 'format=yuv420p']
    if intro_frames:
        # Picture only: the narration keeps its original start and duration.
        filters.append(f'fade=t=in:start_frame=0:'
                       f'nb_frames={max(1, intro_frames - 1)}:color=black')
    if outro_frames:
        # Finish at full black on the last encoded frame; do not extend audio.
        filters.append(f'fade=t=out:start_frame={sum(counts) - outro_frames}:'
                       f'nb_frames={max(1, outro_frames - 1)}:color=black')
    output = Path(job['out']).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    voice = Path(job['voice']).resolve()
    if not voice.is_file():
        raise FileNotFoundError('Reviewed narration file is missing')
    image_paths = [Path(s['image']).resolve() for s in scenes]
    if not all(p.is_file() for p in image_paths):
        raise FileNotFoundError('Reviewed image is missing')
    with tempfile.TemporaryDirectory(prefix='slideshow-', dir=output.parent) as tmp:
        temp = Path(tmp)
        frames = []
        for i, path in enumerate(image_paths):
            with Image.open(path) as original:
                # Native inputs are already landscape. This removes only the
                # subpixel aspect discrepancy, never a camera/zoom margin.
                picture = ImageOps.fit(original.convert('RGB'), (width, height),
                                       method=Image.Resampling.LANCZOS)
            target = temp / f'still-{i:04d}.ppm'
            picture.save(target)
            frames.append(target)
        timeline = []
        for i, count in enumerate(counts):
            incoming = transitions[i - 1] - transitions[i - 1] // 2 if i else 0
            outgoing = transitions[i] // 2 if i < len(transitions) else 0
            hold = count - incoming - outgoing
            if hold:
                timeline.append((frames[i], hold))
            if i < len(transitions) and transitions[i]:
                n = transitions[i]
                with Image.open(frames[i]) as a, Image.open(frames[i + 1]) as b:
                    for k in range(n):
                        mixed = Image.blend(a, b, (k + 1) / (n + 1))
                        # Transient raw frames avoid thousands of costly PNG
                        # compressions for long mixes. TemporaryDirectory removes
                        # them after encoding; source images stay untouched.
                        target = temp / f'fade-{i:04d}-{k:02d}.ppm'
                        mixed.save(target)
                        timeline.append((target, 1))
        assert sum(n for _, n in timeline) == sum(counts)
        lines = ['ffconcat version 1.0']
        for frame, n in timeline:
            lines += [f"file '{frame.name}'", f'option framerate {fps}', f'duration {n / fps:.12f}']
        # Last packet closes the final hold. Exact output frame count below
        # discards this sentinel and prevents a one-frame extension.
        lines += [f"file '{timeline[-1][0].name}'", f'option framerate {fps}']
        sequence = temp / 'timeline.ffconcat'
        sequence.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        candidate = temp / 'final.mp4'
        cmd = [job.get('ffmpeg', 'ffmpeg'), '-nostdin', '-v', 'error', '-y',
               '-threads', '1', '-filter_threads', '1', '-f', 'concat', '-safe', '0',
               '-i', str(sequence), '-i', str(voice), '-map', '0:v:0', '-map', '1:a:0',
               '-vf', ','.join(filters), '-frames:v', str(sum(counts)),
               '-t', f'{sum(counts) / fps:.12f}', '-c:v', 'libx264', '-preset', 'veryfast',
               '-crf', str(job.get('crf', 18)), '-threads', str(max(1, min(4, int(job.get('threads', 2))))),
               '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(candidate)]
        result = subprocess.run(cmd, text=True, encoding='utf-8', capture_output=True)
        if result.returncode:
            raise RuntimeError('Slideshow encode failed: ' + result.stderr[-2000:])
        probe = subprocess.run([job.get('ffprobe', 'ffprobe'), '-v', 'error', '-show_streams',
                                '-show_format', '-of', 'json', str(candidate)], check=True,
                               capture_output=True, text=True, encoding='utf-8')
        info = json.loads(probe.stdout)
        video = next(s for s in info['streams'] if s['codec_type'] == 'video')
        if int(video['nb_frames']) != sum(counts) or (video['width'], video['height']) != (width, height):
            raise RuntimeError('Slideshow size/frame count verification failed')
        if abs(float(info['format']['duration']) - duration) > max(.1, 2 / fps):
            raise RuntimeError('Slideshow narration clock changed')
        candidate.replace(output)
    return {'file': str(output), 'duration': sum(counts) / fps, 'frames': sum(counts),
            'width': width, 'height': height, 'fps': fps, 'camera': 'static',
            'transition': 'crossfade' if any(transitions) else 'cuts',
            'transition_seconds': float(job.get('transition_seconds', .25)),
            'transition_frame_counts': transitions,
            'intro_fade_frames': intro_frames,
            'intro_fade_seconds': intro_frames / fps,
            'outro_fade_frames': outro_frames,
            'outro_fade_seconds': outro_frames / fps,
            'bytes': output.stat().st_size,
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job', type=Path)
    args = parser.parse_args()
    print(json.dumps(render(json.loads(args.job.read_text(encoding='utf-8')))))
