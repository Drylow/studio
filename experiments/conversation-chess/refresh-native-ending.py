#!/usr/bin/env python3
"""Prepare only the final native source fade, preserving the previous project.

The input timeline/manifest and every existing media file remain unchanged. A
fresh output directory receives a derived timeline/manifest, three regenerated
assets and a receipt. This is not a final export or a listening/rights review.
"""

import argparse
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import wave


FPS = 30
RATE = 48000
SOURCE_VIDEO_FILTER = (
    'scale=1848:1080:force_original_aspect_ratio=decrease,'
    'pad=1848:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,'
    'pad=1920:1080:72:0:black'
)


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ending_filters(duration, fade, gain=1):
    require(type(fade) in (int, float) and math.isfinite(fade)
            and 0 < fade <= 1.2 and abs(fade * FPS - round(fade * FPS)) < 1e-6,
            'Fade must be positive, at most 1.2 seconds and aligned to 30 fps')
    require(type(duration) in (int, float) and math.isfinite(duration)
            and duration >= fade and abs(duration * FPS - round(duration * FPS)) < 1e-6,
            'Fade exceeds the final source segment or duration is not frame aligned')
    require(type(gain) in (int, float) and math.isfinite(gain)
            and 0 < gain <= 1, 'Native preparation gain must be in (0, 1]')
    start = max(0, duration - fade)
    video = SOURCE_VIDEO_FILTER + f',fade=t=out:st={start}:d={fade}'
    graphics = f'format=argb,fade=t=out:st={start}:d={fade}:alpha=1'
    audio = (f'aresample={RATE},volume={gain},apad,afade=t=in:st=0:d=0.035,'
             f'afade=t=out:st={start}:d={fade},atrim=end_sample={round(duration * RATE)}')
    return video, graphics, audio


def run(command, log):
    with log.open('w') as output:
        subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True)


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-count_frames', '-show_streams',
        '-show_format', '-of', 'json', str(path)]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--seconds', type=float, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text())
    timeline_path = Path(manifest['timeline_file']).resolve(strict=True)
    timeline = json.loads(timeline_path.read_text())
    source = Path(manifest['original_source']).resolve(strict=True)
    require(digest(source) == manifest['source_sha256'], 'Native source SHA changed')
    require(digest(timeline_path) == manifest['timeline_sha256'], 'Input timeline SHA changed')
    require(manifest['fps'] == FPS, 'Only the native 30 fps workflow is supported')
    require(not timeline.get('conversations'), 'Scoped endings need a complete fresh preparation')
    require(not timeline.get('ending_fade_seconds', 0), 'Input already contains an ending fade')
    indices = [i for i, s in enumerate(manifest['segments']) if s['kind'] == 'source']
    require(indices, 'Manifest has no source segments')
    index = indices[-1]
    original = manifest['segments'][index]
    require(not original.get('fade_out_seconds', 0), 'Final source already contains a fade')
    require(all(s['kind'] == 'outro' for s in manifest['segments'][index + 1:]),
            'Only an outro may follow the final source segment')
    require(original['graphics_type'] == 'alpha_png', 'Expected the unchanged static final overlay')
    frames = original['duration_frames']
    require(type(frames) is int and frames > 0
            and type(original['start_frame']) is int and type(original['end_frame']) is int,
            'Final frame bounds must be positive integer frame coordinates')
    require(frames == original['end_frame'] - original['start_frame'], 'Final frame bounds changed')
    duration = frames / FPS
    require(abs(original['duration'] - duration) < 1e-6, 'Source duration is not frame aligned')
    require(all(type(original[key]) in (int, float) and math.isfinite(original[key])
                and original[key] >= 0
                and abs(original[key] * FPS - round(original[key] * FPS)) < 1e-6
                for key in ('source_in', 'source_out'))
            and abs(original['source_out'] - original['source_in'] - duration) < 1e-6,
            'Final source bounds must match the exact frame duration')
    video_filter, graphics_filter, audio_filter = ending_filters(
        duration, args.seconds, original.get('dialogue_gain', 1))
    existing_media = sorted({Path(s[key]).resolve(strict=True)
                             for s in manifest['segments']
                             for key in ('background_file', 'graphics_file', 'dialogue_audio_file',
                                         'sfx_file', 'music_file') if s.get(key)})
    before = {str(p): digest(p) for p in existing_media}
    require(not args.out.exists(), 'Preserve prior runs: choose a fresh output directory')
    out = args.out.resolve()
    out.mkdir(parents=True)
    before_manifest = out / 'project-manifest.before-ending-fade.json'
    before_timeline = out / 'timeline.before-ending-fade.json'
    before_manifest.write_bytes(manifest_path.read_bytes())
    before_timeline.write_bytes(timeline_path.read_bytes())
    derived_timeline = copy.deepcopy(timeline)
    derived_timeline['ending_fade_seconds'] = args.seconds
    new_timeline = out / 'timeline.json'
    new_timeline.write_text(json.dumps(derived_timeline, indent=2) + '\n')
    background = out / 'project-source-ending-fade.mkv'
    graphics = out / 'project-source-ending-fade-graphics.mov'
    dialogue = out / 'project-source-ending-fade-dialogue.wav'
    commands = [
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-ss',
         str(original['source_in']), '-i', str(source), '-vf', video_filter,
         '-frames:v', str(frames), '-an', '-c:v', 'libx264', '-preset', 'superfast',
         '-crf', '17', '-threads', '2', '-pix_fmt', 'yuv420p', '-r', str(FPS), str(background)],
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-loop', '1',
         '-framerate', str(FPS), '-i', original['graphics_file'], '-vf', graphics_filter,
         '-frames:v', str(frames), '-an', '-c:v', 'qtrle', '-threads', '2', str(graphics)],
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-ss',
         str(original['source_in']), '-i', str(source), '-vn', '-af', audio_filter,
         '-c:a', 'pcm_s16le', '-ar', str(RATE), '-ac', '2', str(dialogue)],
    ]
    for i, command in enumerate(commands):
        run(command, out / f'prepare-{i}.log')
    assets = []
    for path in (background, graphics):
        info = probe(path)
        stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
        require((stream['width'], stream['height']) == (1920, 1080), 'Output geometry changed')
        require(Fraction(stream['avg_frame_rate']) == FPS, 'Output cadence changed')
        require(int(stream['nb_read_frames']) == frames, 'Output frame count changed')
        run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-threads', '1',
             '-i', str(path), '-f', 'null', '-'], out / f'{path.stem}-decode.log')
        assets.append({'file': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size,
                       'frames': frames, 'dimensions': [1920, 1080], 'full_decode_passed': True})
    with wave.open(str(dialogue), 'rb') as audio:
        require((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (RATE, 2, 2),
                'Dialogue format changed')
        samples = audio.getnframes()
    require(samples == frames * (RATE // FPS), 'Dialogue sample count changed')
    assets.append({'file': str(dialogue), 'sha256': digest(dialogue), 'bytes': dialogue.stat().st_size,
                   'samples_per_channel': samples, 'sample_rate': RATE, 'channels': 2})
    require(before == {str(p): digest(p) for p in existing_media}, 'Existing media changed')
    require(digest(manifest_path) == digest(before_manifest), 'Input manifest changed')
    require(digest(timeline_path) == digest(before_timeline), 'Input timeline changed')
    require(digest(source) == manifest['source_sha256'], 'Native source changed during preparation')
    result = copy.deepcopy(manifest)
    result['timeline_file'] = str(new_timeline)
    result['timeline_sha256'] = digest(new_timeline)
    result['segments'][index].update(background_file=str(background), graphics_file=str(graphics),
                                     graphics_type='alpha_mov', dialogue_audio_file=str(dialogue),
                                     fade_out_seconds=args.seconds)
    new_manifest = out / 'project-manifest.json'
    new_manifest.write_text(json.dumps(result, indent=2) + '\n')
    receipt = {'schema': 'conversation-chess-native-ending-refresh-v1',
               'input_manifest': str(manifest_path), 'input_manifest_sha256': digest(manifest_path),
               'input_timeline': str(timeline_path), 'input_timeline_sha256': digest(timeline_path),
               'source': str(source), 'source_sha256': manifest['source_sha256'],
               'project_manifest': str(new_manifest), 'project_manifest_sha256': digest(new_manifest),
               'timeline': str(new_timeline), 'timeline_sha256': digest(new_timeline),
               'changed_timeline_fields': ['ending_fade_seconds'], 'source_segment_index': index,
               'ending_fade_seconds': args.seconds, 'fade_starts_in_last_segment_seconds': duration - args.seconds,
               'duration_frames': frames, 'samples_per_channel': samples,
               'preserved_media_sha256': before, 'existing_media_unchanged': True,
               'regenerated_assets': assets, 'commands': commands,
               'human_audio_listening': False, 'final_render_visual_reviewed': False,
               'final_video_exported': False, 'copyright_clearance_verified': False}
    receipt_path = out / 'ending-refresh-receipt.json'
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'manifest': str(new_manifest), 'receipt': str(receipt_path),
                      'frames': frames, 'samples': samples, 'fade_seconds': args.seconds,
                      'existing_media_unchanged': True}))


if __name__ == '__main__':
    main()
