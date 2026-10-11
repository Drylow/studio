"""Build the two-hour episode from checked narration, original sound and the reviewed loop."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import textwrap
from fractions import Fraction

import numpy as np
from narrate import CHAPTER_TITLES, check_script, request_fields, request_digest

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'output/nature-sleep/garden-production'
DELIVERY = OUT / 'delivery'
RATE = 24000
LENGTH = 7200
VIDEO = DELIVERY / 'Silent-Little-Worlds-The-Lantern-Garden-2-Hours.mp4'
LOOP = OUT / 'loop.mp4'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def loudness(path):
    p = run(['ffmpeg', '-hide_banner', '-nostdin', '-i', str(path), '-af',
             'loudnorm=I=-19:TP=-2:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True)
    return json.JSONDecoder().raw_decode('{' + p.stderr.decode().rsplit('{', 1)[1])[0]


def timestamp(seconds):
    ms = max(0, round(seconds * 1000))
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'


def captions(words):
    cues, group = [], []
    for i, w in enumerate(words):
        proposed = ' '.join(x['w'] for x in group + [w])
        wrapped = textwrap.wrap(proposed, width=42, break_long_words=False)
        if group and (len(wrapped) > 2 or len(proposed) > 78 or w['e'] - group[0]['s'] > 7 or w['s'] - group[-1]['e'] > 1.2):
            cues.append(group)
            group = []
        group.append(w)
        if (w['w'].endswith(('.', '?', '!')) and w['e'] - group[0]['s'] > 1.8) or i == len(words) - 1:
            cues.append(group)
            group = []
    lines, info = [], []
    for i, cue in enumerate(cues):
        start = cue[0]['s']
        last_word_end = cue[-1]['e']
        next_start = cues[i + 1][0]['s'] if i + 1 < len(cues) else LENGTH
        if last_word_end > next_start + .000001:
            raise ValueError('Native word alignment overlaps the next caption; review the alignment')
        # Keep the final word visible; use a small gap only when it fits.
        # Brief captions can remain for one second when the following pause allows it.
        end = min(max(last_word_end + .25, start + 1),
                  max(last_word_end, next_start - .02), next_start, LENGTH)
        text = '\n'.join(textwrap.wrap(' '.join(w['w'] for w in cue), width=42, break_long_words=False))
        if not 0 <= start < end <= LENGTH or len(text.splitlines()) > 2:
            raise ValueError('Caption outside timeline or too many lines')
        lines.append(f'{i + 1}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n')
        info.append({'start': round(start, 3), 'end': round(end, 3), 'text': text})
    (DELIVERY / 'Silent-Little-Worlds-English.srt').write_text('\n'.join(lines), encoding='utf-8')
    return info


def voice():
    DELIVERY.mkdir(parents=True, exist_ok=True)
    scripts = sorted((HERE / 'script').glob('*.txt'))
    if [p.stem for p in scripts] != sorted(CHAPTER_TITLES):
        raise ValueError('The nine reviewed garden chapters are required')
    parts = []
    for script in scripts:
        text = script.read_text()
        check_script(script.stem, text)
        paras = [x.strip() for x in text.split('\n\n') if x.strip()]
        for k in range(0, len(paras), 6):
            result = OUT / 'narration' / f'{script.stem}-{k // 6:02}' / 'result.json'
            data = json.loads(result.read_text())
            fields = request_fields(paras[k:k + 6])
            if (data['id'] != f'{script.stem}-{k // 6:02}' or data['chapter'] != script.stem
                    or data['part'] != k // 6 or data['request_sha256'] != request_digest(fields)):
                raise ValueError(f'{script.name}: narration metadata belongs to a different request or chapter')
            if data['paragraph_word_counts'] != [len(p.split()) for p in paras[k:k + 6]]:
                raise ValueError(f'{script.name}: paragraph boundaries do not match the garden script')
            expected = ' '.join(' '.join(x.split()) for x in paras[k:k + 6])
            if ' '.join(x['w'] for x in data['words']) != expected:
                raise ValueError(f'{script.name}: narration belongs to different script')
            if data['text_match_ratio'] < .94 or sha(ROOT / data['audio']) != data['audio_sha256']:
                raise ValueError('Narration checksum or transcript mismatch')
            if data['words'][-1]['e'] > data['duration'] + .1:
                raise ValueError('Narration truncated at end')
            parts.append(data)
    total = sum(x['duration'] for x in parts)
    paragraph_count = sum(len(x['paragraph_word_counts']) for x in parts)
    # Do not stretch sparse material to fill two hours. All eight stories remain unique.
    pause = (LENGTH - 4 - 12 - total - (len(scripts) - 1) * 4) / (paragraph_count - 1)
    if not .3 <= pause <= 4.5:
        raise ValueError(f'Pause budget {pause:.3f}s needs editorial review, not automatic stretching')
    plan = {'duration': LENGTH, 'voice_source_seconds': round(total, 3), 'paragraph_pause': round(pause, 5),
            'extra_chapter_pause': 4, 'word_count': sum(len(p['words']) for p in parts),
            'paragraphs': paragraph_count, 'parts': [], 'chapters': [], 'insertions': []}
    target = OUT / 'voice-timeline.flac'
    process = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 's16le', '-ar', str(RATE),
                 '-ac', '1', '-i', 'pipe:0', '-c:a', 'flac', '-compression_level', '5', '-y', str(target)], stdin=subprocess.PIPE)
    written = 0
    aligned = []

    def emit(data):
        nonlocal written
        samples = np.asarray(np.clip(data, -1, .999969) * 32768, dtype='<i2')
        process.stdin.write(samples.tobytes())
        written += len(samples)

    def silence(seconds):
        emit(np.zeros(round(seconds * RATE), dtype=np.float32))

    try:
        silence(4)
        previous_chapter = None
        for part_i, part in enumerate(parts):
            chapter = part['chapter']
            if chapter != previous_chapter:
                if previous_chapter is not None:
                    silence(4)
                plan['chapters'].append({'id': chapter, 'title': CHAPTER_TITLES[chapter], 'start': round(written / RATE, 3)})
                previous_chapter = chapter
            start = written / RATE
            path = ROOT / part['audio']
            level_path = path.parent / 'level.json'
            if level_path.exists():
                level = json.loads(level_path.read_text())
            else:
                level = loudness(path)
                write(level_path, level)
            gain_db = min(-19 - float(level['input_i']), -2.5 - float(level['input_tp']))
            audio = np.frombuffer(subprocess.check_output(['ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-i', str(path), '-af', f'volume={gain_db:.6f}dB', '-ar', str(RATE), '-ac', '1', '-f', 'f32le', '-']), dtype='<f4').copy()
            # Tiny edge fades prevent discontinuities when independent generated takes meet silence.
            edge = min(240, len(audio) // 10)
            audio[:edge] *= np.linspace(0, 1, edge)
            audio[-edge:] *= np.linspace(1, 0, edge)
            breaks, word_end = [], 0
            for count in part['paragraph_word_counts'][:-1]:
                word_end += count
                left, right = part['words'][word_end - 1]['e'], part['words'][word_end]['s']
                if right - left < .06:
                    raise ValueError(f'{part["id"]}: paragraph gap too short for a clean edit')
                cut = round((left + right) * .5 * RATE)
                breaks.append((word_end, cut))
                a, b = max(0, cut - 120), min(len(audio), cut + 120)
                rms = float(np.sqrt(np.mean(audio[a:b] ** 2)))
                plan['insertions'].append({'part': part['id'], 'after_word': word_end, 'native_gap': round(right - left, 3),
                                           'cut_rms_dbfs': round(20 * math.log10(max(rms, 1e-9)), 2)})
                if rms > .015:
                    raise ValueError(f'{part["id"]}: pause cut has audible energy; inspect before inserting')
                audio[max(0, cut - 120):cut] *= np.linspace(1, 0, min(120, cut))
                audio[cut:min(len(audio), cut + 120)] *= np.linspace(0, 1, min(120, len(audio) - cut))
            for w_i, w in enumerate(part['words']):
                delta = start + sum(pause for wi, _ in breaks if w_i >= wi)
                aligned.append({'w': w['w'], 's': w['s'] + delta, 'e': w['e'] + delta})
            cursor = 0
            for _, cut in breaks:
                emit(audio[cursor:cut])
                silence(pause)
                cursor = cut
            emit(audio[cursor:])
            if part_i != len(parts) - 1:
                silence(pause)
            plan['parts'].append({'id': part['id'], 'start': round(start, 3), 'end': round(written / RATE, 3),
                                  'gain_db': round(gain_db, 3), 'source_sha256': part['audio_sha256'],
                                  'transcript_match': part['text_match_ratio']})
            print(f'{part["id"]}: assembled at {written / RATE / 60:.1f} min', flush=True)
        remaining = LENGTH * RATE - written
        if not 10 * RATE <= remaining <= 15 * RATE:
            raise ValueError(f'Unexpected final padding {remaining / RATE}')
        if aligned[-1]['e'] > LENGTH - 12:
            raise ValueError('The final word would enter the closing fade; review the pause budget')
        emit(np.zeros(remaining, dtype=np.float32))
    finally:
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError('Voice encoding failed')
    plan['words_last_end'] = round(aligned[-1]['e'], 3)
    plan['voice_timeline_sha256'] = sha(target)
    plan['captions'] = len(captions(aligned))
    write(OUT / 'timeline-words.json', aligned)
    write(OUT / 'timeline.json', plan)
    # MP4 chapters need no flashing on-screen title cards.
    meta = [';FFMETADATA1', 'title=The Lantern Garden', 'artist=Silent Little Worlds']
    for i, c in enumerate(plan['chapters']):
        start = 0 if i == 0 else round(c['start'] * 1000)
        end = round(plan['chapters'][i + 1]['start'] * 1000) if i + 1 < len(plan['chapters']) else LENGTH * 1000
        meta += ['[CHAPTER]', 'TIMEBASE=1/1000', f'START={start}', f'END={end}', 'title=' + c['title']]
    (OUT / 'chapters.ffmeta').write_text('\n'.join(meta) + '\n')
    print(json.dumps({k: plan[k] for k in ('word_count', 'paragraphs', 'voice_source_seconds', 'paragraph_pause', 'captions')}))


def mix():
    # Sources are stereo -24 LUFS beds; speech remains clear with quiet accompaniment.
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-i', str(OUT / 'voice-timeline.flac'),
               '-stream_loop', '-1', '-i', str(OUT / 'ambience/ambience.flac'),
               '-stream_loop', '-1', '-i', str(OUT / 'ambience/music.flac'), '-filter_complex',
               '[0:a]aformat=sample_rates=48000:channel_layouts=stereo[v];'
               '[1:a]volume=-15dB,aformat=sample_rates=48000:channel_layouts=stereo[a];'
               '[2:a]volume=-20dB,aformat=sample_rates=48000:channel_layouts=stereo[m];'
               '[v][a][m]amix=inputs=3:normalize=0:duration=first,'
               'afade=t=in:st=0:d=4,afade=t=out:st=7188:d=12[out]',
               '-map', '[out]', '-t', str(LENGTH), '-c:a', 'aac', '-b:a', '160k', '-y', str(OUT / 'final-audio.m4a')]
    run(command)
    level = loudness(OUT / 'final-audio.m4a')
    write(OUT / 'mix-level.json', level)
    if float(level['input_tp']) > -1 or not -23 < float(level['input_i']) < -16:
        raise ValueError('Final mix loudness outside review range')
    print(json.dumps(level))


def loop_info():
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format',
                                                '-show_streams', '-of', 'json', str(LOOP)]))
    streams = [s for s in probe['streams'] if s['codec_type'] == 'video']
    if len(streams) != 1:
        raise ValueError('The garden loop must contain one video stream')
    video = streams[0]
    if (video['width'] != 1920 or video['height'] != 1080
            or Fraction(video['r_frame_rate']) != 30 or Fraction(video['avg_frame_rate']) != 30):
        raise ValueError('The garden loop must be constant 1920x1080 at 30 fps')
    duration = float(video.get('duration', probe['format']['duration']))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid garden loop duration')
    frames = video.get('nb_frames')
    if not frames or frames == 'N/A':
        frames = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                          '-count_frames', '-show_entries', 'stream=nb_read_frames',
                                          '-of', 'default=nw=1:nk=1', str(LOOP)], text=True).strip()
    frames = int(frames)
    if abs(frames / 30 - duration) > .04:
        raise ValueError('Garden loop frame count and duration disagree')
    return {'file': str(LOOP.relative_to(ROOT)), 'duration_seconds': duration,
            'frames': frames, 'sha256': sha(LOOP), 'width': 1920, 'height': 1080, 'fps': 30}


def package():
    if (HERE / 'HOLD.json').exists():
        raise RuntimeError('Animated preview is awaiting user approval; do not start the long export')
    source_loop = loop_info()
    for name in ('technical-review.json', 'visual-review.json'):
        review = json.loads((OUT / 'qa' / name).read_text())
        assert review['sha256'] == source_loop['sha256']
        assert review.get('technical_pass') or review.get('approved_as_render_background')
    DELIVERY.mkdir(parents=True, exist_ok=True)
    run([sys.executable, str(HERE / 'visualizer.py'), '--background', str(LOOP),
         '--voice', str(OUT / 'voice-timeline.flac'), '--mix', str(OUT / 'final-audio.m4a'),
         '--chapters', str(OUT / 'chapters.ffmeta'), '--duration', str(LENGTH),
         '--allow-long-render', '--warm-cache', '--threads', '4',
         '--out', str(OUT / 'visualizer-final'), '--final-path', str(VIDEO)])
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', '9', '-i', str(VIDEO), '-frames:v', '1',
         '-q:v', '2', '-y', str(DELIVERY / 'Silent-Little-Worlds-Thumbnail.jpg')])
    print(json.dumps({'video': str(VIDEO.relative_to(ROOT)), 'bytes': VIDEO.stat().st_size}))


def verify():
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-show_chapters', '-of', 'json', str(VIDEO)]))
    video = next(x for x in probe['streams'] if x['codec_type'] == 'video')
    audio = next(x for x in probe['streams'] if x['codec_type'] == 'audio')
    assert abs(float(probe['format']['duration']) - LENGTH) < .06
    assert video['width'] == 1920 and video['height'] == 1080 and video['r_frame_rate'] == '30/1'
    assert int(video['nb_frames']) == 216000
    assert audio['channels'] == 2 and int(audio['sample_rate']) == 48000
    assert len(probe['chapters']) == len(CHAPTER_TITLES)
    source = json.loads((OUT / 'package-source.json').read_text())
    assert source['loop']['sha256'] == sha(LOOP)
    assert source['audio_sha256'] == sha(OUT / 'final-audio.m4a')
    assert source['chapters_sha256'] == sha(OUT / 'chapters.ffmeta')
    video_sha = sha(VIDEO)
    profile_path = ROOT / source['visualizer_profile']['file']
    assert sha(profile_path) == source['visualizer_profile']['sha256']
    profile = json.loads(profile_path.read_text())
    assert profile['sha256'] == source['video_sha256'] == video_sha
    assert profile['background_sha256'] == source['loop']['sha256']
    assert profile['mix_sha256'] == source['audio_sha256']
    assert profile['chapters_sha256'] == source['chapters_sha256']
    assert profile['voice_sha256'] == sha(OUT / 'voice-timeline.flac')
    assert profile['narrator_only_rms'] and not profile['background_is_still']
    assert profile['full_decode_pass'] and profile['full_decode_streams'] == ['0:v:0', '0:a:0']
    assert profile['frames'] == 216000 and profile['duration_seconds'] == LENGTH
    # The renderer has already decoded both streams of this exact SHA in full.
    # Reuse that evidence rather than repeating the same two-hour decode.
    report = {'technical_pass': True, 'sha256': video_sha, 'bytes': VIDEO.stat().st_size,
              'duration': float(probe['format']['duration']), 'video_frames': int(video['nb_frames']),
              'resolution': [1920, 1080], 'fps': 30, 'audio_hz': 48000, 'audio_channels': 2,
              'full_av_decode': True, 'chapters': len(probe['chapters']), 'mix': json.loads((OUT / 'mix-level.json').read_text()),
              'source_loop': source['loop'],
              'visualizer_profile': source['visualizer_profile'],
              'note': 'Full AV decode recorded by the renderer and bound to this exact SHA. Separate visual review is still required.'}
    write(OUT / 'technical-review.json', report)
    print(json.dumps(report))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('step', choices=['voice', 'mix', 'package', 'verify'])
    globals()[p.parse_args().step]()
