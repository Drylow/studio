#!/usr/bin/env python3
"""Render an original, understated voice-reactive orb over the garden loop.

No browser frames: cache small RGBA sprites, stream them to FFmpeg and
overlay on the existing video. The envelope uses narration alone, never
the ambience/music. Long renders require an explicit command-line switch.
"""

from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'output/nature-sleep/garden-production'
FPS = 30
AUDIO_RATE = 24000
SPRITE_SIZE = 224
SUPERSAMPLE = 2
CENTER = (960, 540)
PHASE_STEPS = 128
AMPLITUDE_STEPS = 25
MORPH_PERIOD = 12.8


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-show_chapters', '-of', 'json', str(path)]))


def narration_envelope(voice, start, duration):
    """Stream real PCM into one RMS value per frame, then apply slow ballistics."""
    frames = round(duration * FPS)
    frame_samples = AUDIO_RATE // FPS
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin',
           '-ss', str(start), '-i', str(voice), '-t', str(duration),
           '-ar', str(AUDIO_RATE), '-ac', '1', '-f', 'f32le', 'pipe:1']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    values = []
    try:
        # One second at a time; a two-hour job never retains two hours of PCM.
        while True:
            block = p.stdout.read(AUDIO_RATE * 4)
            if not block:
                break
            pcm = np.frombuffer(block, dtype='<f4')
            remainder = len(pcm) % frame_samples
            if remainder:
                pcm = np.pad(pcm, (0, frame_samples - remainder))
            squared = pcm.reshape(-1, frame_samples).astype(np.float64)**2
            values.extend(np.sqrt(np.mean(squared, axis=1)).tolist())
    finally:
        p.stdout.close()
        error = p.stderr.read().decode(errors='replace')
        p.stderr.close()
    if p.wait() != 0:
        raise RuntimeError('Narrator decoding failed: ' + error[-400:])
    if not values:
        raise ValueError('Narrator contains no decodable audio')
    rms = np.zeros(frames, dtype=np.float32)
    copied = min(frames, len(values))
    rms[:copied] = values[:copied]
    dbfs = (20 * np.log10(np.maximum(rms, 1e-9))).astype(np.float32)
    speech = dbfs[dbfs > -56]
    if len(speech) < 3:
        raise ValueError('No speech energy found for the visualizer')
    reference = float(np.clip(np.percentile(speech, 90), -34, -6))
    floor = max(-56.0, reference - 28.0)
    target = np.clip((dbfs - floor) / (reference - floor), 0, 1)
    target[dbfs < -58] = 0
    # 90 ms attack / 430 ms release: no flashes on consonants or tiny breaths.
    attack = math.exp(-1 / (FPS * .09))
    release = math.exp(-1 / (FPS * .43))
    level, smooth = 0.0, np.zeros(frames, dtype=np.float32)
    for i, value in enumerate(target):
        coefficient = attack if value > level else release
        level = coefficient * level + (1 - coefficient) * float(value)
        smooth[i] = level
    return rms, dbfs, smooth, reference


class OrbSprites:
    def __init__(self, cache_size=3200):
        side = SPRITE_SIZE * SUPERSAMPLE
        axis = (np.arange(side, dtype=np.float32) + .5) / SUPERSAMPLE - SPRITE_SIZE / 2
        x, y = np.meshgrid(axis, axis)
        self.radius = np.hypot(x, y)
        self.theta = np.arctan2(y, x)
        self.get = lru_cache(maxsize=cache_size)(self._get)

    def _get(self, phase_step, amplitude_step):
        """An airy ring, transparent in the centre, around 130–145 px visible."""
        theta, radial = self.theta, self.radius
        phase = phase_step / PHASE_STEPS * 2 * np.pi
        energy = amplitude_step / (AMPLITUDE_STEPS - 1)
        radius = 57 + 5.5 * energy
        contour = (radius + (1.4 + 1.25 * energy) * np.sin(3 * theta + phase)
                   + (0.8 + 0.8 * energy) * np.sin(5 * theta - phase)
                   + .75 * np.sin(2 * theta + 2 * phase))
        distance = radial - contour
        # A thin soft edge plus a broad quiet halo, never an opaque disc.
        edge = .73 * np.exp(-(distance / 1.75)**2)
        halo = .115 * np.exp(-(distance / 6.8)**2)
        inner = .12 * np.exp(-((distance + 4.2) / 1.25)**2)
        alpha = np.clip(edge + halo + inner, 0, .90)
        # Slow colour migration stays within pale gold, mint and lavender.
        colors = np.array([[237, 217, 174], [181, 223, 206], [217, 207, 235]], dtype=np.float32)
        weights = np.stack([np.exp(1.45 * np.cos(theta - offset + .22 * np.sin(phase)))
                            for offset in [0, 2.1, 4.2]], axis=-1)
        weights /= weights.sum(axis=-1, keepdims=True)
        rgb = weights @ colors
        rgb = .82 * rgb + .18 * np.array([250, 245, 233], dtype=np.float32)
        rgba = np.concatenate((rgb, (255 * alpha)[..., None]), axis=-1)
        # Supersampled edges prevent quantisation shimmer at this small size.
        im = Image.fromarray(np.uint8(np.clip(rgba, 0, 255)), 'RGBA')
        im = im.resize((SPRITE_SIZE, SPRITE_SIZE), Image.Resampling.LANCZOS)
        return im.tobytes()

    def key(self, index, amplitude):
        phase = round((index / FPS / MORPH_PERIOD) * PHASE_STEPS) % PHASE_STEPS
        level = int(np.clip(round(float(amplitude) * (AMPLITUDE_STEPS - 1)), 0, AMPLITUDE_STEPS - 1))
        return phase, level

    def frame(self, index, amplitude):
        return self.get(*self.key(index, amplitude))


def voice_gain(voice, start, duration):
    level = voice.parent / 'level.json'
    if level.is_file():
        data = json.loads(level.read_text())
        return min(-19 - float(data['input_i']), -2.5 - float(data['input_tp']))
    measured = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-nostats', '-ss', str(start),
                              '-i', str(voice), '-t', str(duration),
                              '-af', 'loudnorm=I=-19:TP=-2:LRA=11:print_format=json',
                              '-f', 'null', '-'], check=True, capture_output=True, text=True)
    data = json.loads(measured.stderr[measured.stderr.rfind('{'):measured.stderr.rfind('}') + 1])
    return min(-19 - float(data['input_i']), -2.5 - float(data['input_tp']))


def render(args):
    background, voice, directory = args.background.resolve(), args.voice.resolve(), args.out.resolve()
    if args.duration <= 0 or args.duration > 7200:
        raise ValueError('Duration must be between zero and two hours')
    if args.duration > 20 and not args.allow_long_render:
        raise ValueError('Only a short prototype is allowed until visual review; pass --allow-long-render explicitly afterwards')
    if args.final_path and (not args.mix or not args.chapters):
        raise ValueError('--final-path requires the completed --mix and --chapters')
    if args.duration > 20 and not args.final_path:
        raise ValueError('A long render must encode directly to --final-path, not make a duplicate intermediate movie')
    if args.final_path and args.internal_test:
        raise ValueError('An internal test cannot be a final export')
    if args.start < 0:
        raise ValueError('Negative voice start is invalid')
    archive = ROOT / 'output/nature-sleep/night-train-production'
    if voice.is_relative_to(archive) and not args.internal_test:
        raise ValueError('Archived train audio is permitted only with --internal-test, never as a garden delivery')
    still = background.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}
    if still and not args.internal_test:
        raise ValueError('A static background is only allowed for an internal performance test')
    bg_probe = probe(background)
    video = next(s for s in bg_probe['streams'] if s['codec_type'] == 'video')
    if video['width'] != 1920 or video['height'] != 1080:
        raise ValueError('Background must be the full-resolution 1920x1080 scene')
    if not still and video['r_frame_rate'] != '30/1':
        raise ValueError('Animated background must be 30 fps')
    voice_probe = probe(voice)
    if args.start + args.duration > float(voice_probe['format']['duration']) + .05:
        raise ValueError('Requested preview extends past the narrator audio')
    mix, chapters = None, None
    if args.mix:
        mix = args.mix.resolve()
        mix_probe = probe(mix)
        mix_audio = next(s for s in mix_probe['streams'] if s['codec_type'] == 'audio')
        if mix_audio['codec_name'] != 'aac':
            raise ValueError('The completed mix must already be AAC for audio stream copy')
        if args.start + args.duration > float(mix_probe['format']['duration']) + .05:
            raise ValueError('The completed mix is shorter than the requested render')
    if args.chapters:
        chapters = args.chapters.resolve()
        chapter_probe = probe(chapters)
        if len(chapter_probe.get('chapters', [])) != 9:
            raise ValueError('The completed chapter metadata must contain the nine garden chapters')
    directory.mkdir(parents=True, exist_ok=True)
    target = args.final_path.resolve() if args.final_path else directory / 'garden-voice-orb-preview.mp4'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('Refusing to overwrite an existing visualizer preview')
    frames = round(args.duration * FPS)
    duration = frames / FPS
    started = time.monotonic()
    rms, dbfs, amplitude, reference = narration_envelope(voice, args.start, duration)
    envelope_seconds = time.monotonic() - started
    np.savez_compressed(directory / 'narrator-envelope.npz', rms=rms, dbfs=dbfs, amplitude=amplitude)
    sprites = OrbSprites(args.sprite_cache)
    warm_started = time.monotonic()
    if args.warm_cache:
        keys = sorted({sprites.key(i, level) for i, level in enumerate(amplitude)})
        if len(keys) > args.sprite_cache:
            raise ValueError('The sprite cache is too small to prewarm every required state')
        for key in keys:
            sprites.get(*key)
    warm_seconds = time.monotonic() - warm_started
    cache_before_render = sprites.get.cache_info()
    preview_gain = None if mix else voice_gain(voice, args.start, duration)
    x, y = CENTER[0] - SPRITE_SIZE // 2, CENTER[1] - SPRITE_SIZE // 2
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-nostdin', '-n',
               '-threads', str(args.threads), '-filter_complex_threads', '1']
    command += (['-framerate', str(FPS)] if still else ['-stream_loop', '-1'])
    background_filter = ('loop=loop=-1:size=1:start=0,setpts=N/(30*TB)' if still else 'setpts=PTS-STARTPTS')
    command += ['-i', str(background), '-thread_queue_size', '64', '-f', 'rawvideo', '-pix_fmt', 'rgba',
                '-s:v', f'{SPRITE_SIZE}x{SPRITE_SIZE}', '-r', str(FPS), '-i', 'pipe:0']
    # Even a zero seek drops AAC's negative-time priming packet in stream-copy
    # mode. Keep it at the timeline origin so decoded samples remain identical.
    if args.start:
        command += ['-ss', str(args.start)]
    command += ['-t', str(duration), '-i', str(mix or voice)]
    if chapters:
        command += ['-i', str(chapters)]
    graph = (f'[0:v]{background_filter},format=yuv420p[b];'
             '[1:v]setpts=PTS-STARTPTS,format=yuva420p[o];'
             f'[b][o]overlay=x={x}:y={y}:shortest=1:format=yuv420[v]')
    if not mix:
        graph += (f';[2:a]volume={preview_gain:.6f}dB,afade=t=in:st=0:d=0.06,'
                  f'afade=t=out:st={duration - .12:.6f}:d=0.12[a]')
    command += ['-filter_complex', graph, '-map', '[v]', '-map', '2:a:0' if mix else '[a]']
    if chapters:
        command += ['-map_metadata', '3', '-map_chapters', '3']
    command += ['-t', str(duration), '-frames:v', str(frames), '-r', str(FPS), '-fps_mode:v', 'cfr', '-c:v', 'libx264',
                '-crf', str(args.crf), '-preset', args.preset, '-threads', str(args.threads)]
    command += ['-c:a', 'copy'] if mix else ['-c:a', 'aac', '-b:a', '128k']
    command += ['-movflags', '+faststart', str(target)]
    render_started = time.monotonic()
    log = directory / 'render.log'
    with log.open('wb') as stderr:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=stderr)
        try:
            for index, level in enumerate(amplitude):
                process.stdin.write(sprites.frame(index, level))
                if index and index % 300 == 0:
                    print(f'Visualizer: {index}/{frames} frames', flush=True)
            process.stdin.close()
        except BaseException:
            process.kill()
            process.wait()
            raise
        if process.wait() != 0:
            raise RuntimeError('Visualizer encoding failed; inspect the private render.log')
    render_seconds = time.monotonic() - render_started
    output = probe(target)
    out_video = next(s for s in output['streams'] if s['codec_type'] == 'video')
    assert int(out_video['nb_frames']) == frames
    assert out_video['avg_frame_rate'] == f'{FPS}/1'
    assert abs(float(out_video['duration']) - duration) < .001
    assert abs(float(output['format']['duration']) - duration) < .06
    if chapters and duration == 7200:
        assert len(output.get('chapters', [])) == 9
    decode_command = ['ffmpeg', '-v', 'error', '-xerror', '-threads', str(args.threads),
                      '-i', str(target), '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-']
    decode_started = time.monotonic()
    subprocess.run(decode_command, check=True)
    decode_seconds = time.monotonic() - decode_started
    for label, index in [('quiet', int(np.argmin(amplitude))), ('speaking', int(np.argmax(amplitude))),
                         ('middle', frames // 2)]:
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-ss', str(index / FPS), '-i', str(target),
                        '-frames:v', '1',
                        str(directory / f'{label}.png')], check=True)
    cache = sprites.get.cache_info()
    report = {
        'duration_seconds': duration, 'frames': frames, 'fps': FPS, 'resolution': [1920, 1080],
        'probed_video_duration_seconds': float(out_video['duration']),
        'probed_container_duration_seconds': float(output['format']['duration']),
        'center': list(CENTER), 'sprite_size': SPRITE_SIZE,
        'visual': 'Original soft transparent ring; pale gold/mint/lavender; no logo or text.',
        'envelope_source': str(voice.relative_to(ROOT)) if voice.is_relative_to(ROOT) else voice.name,
        'voice_start_seconds': args.start, 'voice_sha256': sha(voice),
        'output_file': str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else target.name,
        'mix_audio_stream_copied': bool(mix), 'mix_sha256': sha(mix) if mix else None,
        'preview_voice_gain_db': preview_gain,
        'chapters_sha256': sha(chapters) if chapters else None,
        'output_chapters': len(output.get('chapters', [])),
        'background_sha256': sha(background), 'background_is_still': still,
        'background_duration_seconds': None if still else float(bg_probe['format']['duration']),
        'narrator_only_rms': True, 'amplitude_reference_dbfs': reference,
        'attack_seconds': .09, 'release_seconds': .43,
        'amplitude_min': float(amplitude.min()), 'amplitude_max': float(amplitude.max()),
        'max_per_frame_amplitude_change': float(np.max(np.abs(np.diff(amplitude)))),
        'cache_hits': cache.hits, 'cache_misses': cache.misses,
        'render_cache_hits': cache.hits - cache_before_render.hits,
        'render_cache_misses': cache.misses - cache_before_render.misses,
        'cache_prewarmed': bool(args.warm_cache), 'cache_warm_seconds': round(warm_seconds, 3),
        'maximum_sprite_cache_bytes': args.sprite_cache * SPRITE_SIZE * SPRITE_SIZE * 4,
        'envelope_processing_seconds': round(envelope_seconds, 3),
        'render_wall_seconds': round(render_seconds, 3),
        'render_speed_realtime': round(duration / render_seconds, 3),
        'linear_estimate_two_hours_minutes': round(render_seconds / duration * 120, 1),
        'estimate_note': 'Measured encoder/compositor wall time. Prewarming is reported separately when enabled; extrapolation is not a deadline.',
        'codec': 'h264', 'crf': args.crf, 'preset': args.preset, 'encoder_threads': args.threads,
        'bytes': target.stat().st_size, 'sha256': sha(target), 'full_decode_pass': True,
        'full_decode_streams': ['0:v:0', '0:a:0'],
        'full_decode_command': decode_command, 'full_decode_wall_seconds': round(decode_seconds, 3),
        'internal_test': bool(args.internal_test), 'visual_review_complete': False,
        'long_render_started': duration > 20,
    }
    profile_path = directory / 'profile.json'
    profile_path.write_text(json.dumps(report, indent=2) + '\n')
    if args.final_path:
        # A short mux test must never replace the two-hour production receipt.
        package_path = (OUT if duration == 7200 else directory) / 'package-source.json'
        source_frames = video.get('nb_frames')
        if not source_frames or source_frames == 'N/A':
            source_frames = subprocess.check_output([
                'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
                '-show_entries', 'stream=nb_read_frames', '-of', 'default=nw=1:nk=1',
                str(background)], text=True).strip()
        package = {
            'loop': {
                'file': str(background.relative_to(ROOT)) if background.is_relative_to(ROOT) else str(background),
                'duration_seconds': float(video.get('duration', bg_probe['format']['duration'])),
                'frames': int(source_frames), 'sha256': report['background_sha256'],
                'width': video['width'], 'height': video['height'], 'fps': FPS,
            },
            'audio_sha256': report['mix_sha256'],
            'chapters_sha256': report['chapters_sha256'],
            'video_sha256': report['sha256'],
            'visualizer_profile': {
                'file': str(profile_path.relative_to(ROOT)) if profile_path.is_relative_to(ROOT) else str(profile_path),
                'sha256': sha(profile_path),
            },
        }
        package_path.write_text(json.dumps(package, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--background', type=Path, default=OUT / 'loop.mp4')
    p.add_argument('--voice', type=Path, default=OUT / 'narration/00-welcome-00/voice.mp3')
    p.add_argument('--out', type=Path, default=OUT / 'visualizer-test')
    p.add_argument('--duration', type=float, default=16)
    p.add_argument('--start', type=float, default=0)
    p.add_argument('--crf', type=int, choices=[20, 21, 22], default=22)
    p.add_argument('--preset', choices=['veryfast', 'superfast', 'ultrafast'], default='veryfast')
    p.add_argument('--threads', type=int, choices=[2, 4], default=2)
    p.add_argument('--sprite-cache', type=int, choices=[384, 3200, 4096], default=4096)
    p.add_argument('--warm-cache', action='store_true', help='Prepare all needed small sprites before timing the compositor/encoder')
    p.add_argument('--mix', type=Path, help='Completed AAC mix to stream-copy; RMS still comes from --voice')
    p.add_argument('--chapters', type=Path, help='Completed nine-chapter FFmetadata file')
    p.add_argument('--final-path', type=Path, help='Encode directly here; requires --mix and --chapters')
    p.add_argument('--internal-test', action='store_true')
    p.add_argument('--allow-long-render', action='store_true')
    render(p.parse_args())
