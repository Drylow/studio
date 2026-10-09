"""OVNI picture rendering with the existing studio audio mix and frame clock."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

from PIL import Image, ImageOps

from services import media, render
from services.ovni_timeline import frame_plan


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def cached_picture(picture, receipt_path, frames):
    if not picture.is_file() or not receipt_path.is_file():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        return receipt['frames'] == frames and receipt['picture_sha256'] == digest(picture)
    except (OSError, ValueError, KeyError):
        return False


def runtime():
    python = Path(os.environ.get('OVNI_PYTHON') or
                  Path.home() / '.codex/runtimes/ovni-20261009/python.exe')
    if not python.is_file():
        raise media.MediaError('OVNI runtime missing: run production/ovni.ps1 -Action Install. '
                               'No automatic switch to the CPU renderer.')
    env = os.environ.copy()
    prefix = python.parent
    env['PATH'] = os.pathsep.join([str(prefix), str(prefix / 'Library/bin'),
                                  str(prefix / 'Scripts'), env.get('PATH', '')])
    env['CONDA_PREFIX'] = str(prefix)
    env['CUDA_PATH'] = str(prefix / 'Library')
    return python, env


def render_video(workdir, scenes, voice_path, out_path, *, width=1920, height=1080, fps=30,
                 motion='auto', motion_strength=0.12, transition='fade', transition_dur=0.35,
                 words=None, captions=None, overlays=None, music_path=None, music_volume=0.12,
                 normalize=True, quality='fast', tail=0.6, layout=None, progress=None, cancelled=None,
                 fx=None, sfx_events=None):
    if layout or fx or overlays or (captions or {}).get('mode', 'none') != 'none':
        raise media.MediaError('This OVNI path supports historical full-frame images and audio, '
                               'not board layouts, graphic overlays or burned-in captions. '
                               'These options are never silently dropped.')
    if (not all(math.isfinite(v) and int(v) == v and v > 0 for v in (width, height, fps))
            or width % 2 or height % 2 or tail < 0):
        raise ValueError('Use even picture dimensions, an integer frame rate and a nonnegative tail')
    if not math.isfinite(motion_strength) or not math.isfinite(tail):
        raise ValueError('Camera strength and audio tail must be finite')
    width, height, fps = int(width), int(height), int(fps)
    python, env = runtime()
    kernels = python.parent / 'Lib/site-packages/ovni/kernels/compiled/all_kernels.ptx'
    if not kernels.is_file():
        raise media.MediaError('OVNI kernels missing: run production/ovni.ps1 -Action Compile')
    work = Path(workdir).resolve() / 'ovni'
    work.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    def tick(fraction, message):
        if cancelled and cancelled():
            raise media.Cancelled('OVNI render cancelled')
        if progress:
            progress(fraction, message)

    duration = media.duration(voice_path) + tail
    motions = render.pick_motions(len(scenes), motion, seed=len(scenes))
    selected = [{**s, 'motion': s.get('motion') or motions[i]} for i, s in enumerate(scenes)]
    plan = frame_plan(selected, duration, int(fps), transition, transition_dur)
    ready = work / 'images'
    ready.mkdir(exist_ok=True)
    for index, shot in enumerate(plan):
        tick(0.02 * index / len(plan), f'Preparing OVNI image {index + 1}/{len(plan)}')
        source = Path(shot['image']).resolve()
        source_hash = digest(source)
        with Image.open(source) as image:
            if 'A' in image.getbands() and image.getchannel('A').getextrema() != (255, 255):
                raise media.MediaError('Nonopaque image requires normalization and visual approval before OVNI')
            if image.size == (width, height) and image.mode == 'RGB':
                target = source
            else:
                target = ready / f'{source_hash}-{width}x{height}.png'
            if target != source and not target.exists():
                fitted = ImageOps.fit(image.convert('RGB'), (width, height), Image.Resampling.LANCZOS)
                fitted.save(target)
        shot.update({'image': str(target), 'sha256': digest(target),
                     'source': str(source), 'source_sha256': source_hash})
    config = {'scenes': plan, 'width': width, 'height': height, 'fps': int(fps),
              'motion_strength': motion_strength, 'preset': 'P5' if quality == 'high' else 'P3',
              'bitrate': '12M' if quality == 'high' else '8M',
              'version': [digest(kernels), digest(Path(__file__)), digest(Path(__file__).with_name('ovni_worker.py')),
                          digest(Path(__file__).with_name('ovni_timeline.py'))]}
    tag = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:20]
    cache = work / tag
    cache.mkdir(exist_ok=True)
    raw, picture = cache / 'video.h264', cache / 'picture.mp4'
    result_path = cache / 'worker-result.json'
    config.update({'raw_output': str(raw), 'progress': str(cache / 'progress.json'),
                   'result': str(result_path)})
    request = cache / 'request.json'
    save(request, config)
    expected_frames = sum(s['frames'] for s in plan)
    reused = cached_picture(picture, result_path, expected_frames)
    if not reused:
        result_path.unlink(missing_ok=True)
        Path(config['progress']).unlink(missing_ok=True)
        worker = Path(__file__).with_name('ovni_worker.py')
        with (cache / 'worker.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([str(python), str(worker), str(request)], env=env,
                                       stdout=log, stderr=log, creationflags=media._NO_WINDOW)
            reported = -1
            try:
                while process.poll() is None:
                    done = 0
                    if Path(config['progress']).exists():
                        try:
                            done = json.loads(Path(config['progress']).read_text(encoding='utf-8'))['frames']
                        except (OSError, ValueError):
                            pass
                    fraction = 0.02 + 0.82 * done / expected_frames
                    if cancelled and cancelled():
                        raise media.Cancelled('OVNI render cancelled')
                    if int(fraction * 100) != reported:
                        tick(fraction, 'OVNI GPU rendering')
                        reported = int(fraction * 100)
                    time.sleep(0.2)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        if process.returncode:
            error = (cache / 'worker.log').read_text(encoding='utf-8')[-2500:]
            raise media.MediaError('OVNI worker failed; no CPU fallback:\n' + error)
        receipt = json.loads(result_path.read_text(encoding='utf-8'))
        if receipt['frames'] != expected_frames:
            raise media.MediaError('OVNI worker returned the wrong frame count')
        temporary = cache / 'picture.tmp.mp4'
        # OVNI's RGB->NV12 kernel is limited-range BT.709; declare it in H.264 VUI.
        media.run(['-r', str(fps), '-i', str(raw), '-c:v', 'copy', '-an',
                   '-bsf:v', 'h264_metadata=video_full_range_flag=0:colour_primaries=1:'
                             'transfer_characteristics=1:matrix_coefficients=1',
                   '-video_track_timescale', str(int(fps) * 1000), str(temporary)], cancelled=cancelled)
        temporary.replace(picture)
        receipt['picture_sha256'] = digest(picture)
        save(result_path, receipt)
    tick(0.87, 'Mixing narration and exporting OVNI picture')
    sounds = None
    if sfx_events:
        from services import sfx
        sounds = sfx.build_track(sfx_events, duration, str(work / 'sfx.wav'))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    render._final_pass(str(work), [str(picture)], None, transition_dur, voice_path, str(out_path),
                       duration, None, music_path, music_volume, normalize, quality, fps,
                       cancelled=cancelled, sfx=sounds)
    receipt = json.loads(result_path.read_text(encoding='utf-8'))
    result = {'path': str(out_path), 'duration': duration, 'backend': 'ovni',
              'video_frames': sum(s['frames'] for s in plan), 'picture_cache': str(picture),
              'worker_seconds': receipt['seconds'], 'render_seconds': time.perf_counter() - started,
              'preset': config['preset'], 'bitrate': config['bitrate'],
              'picture_cache_reused': reused,
              'qa_pending': True, 'publication_ready': False}
    save(work / 'render-result.json', result)
    tick(1, 'OVNI render complete; montage review still required')
    return result
