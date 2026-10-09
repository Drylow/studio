"""One isolated GPU process per render; no prompting or creative decisions."""
import hashlib
import json
from pathlib import Path
import sys
import time

import cupy as cp
import ovni
from ovni.ops import linear_blend, rgb_to_nv12, scale_translate

from ovni_timeline import camera, fade_weight


def save(path, value, required=True):
    path = Path(path)
    temporary = path.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    # Windows readers/antivirus can briefly deny replacement of an open file.
    for attempt in range(10):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                if required:
                    raise
                return
            time.sleep(0.02)


def run(manifest):
    started = time.perf_counter()
    ovni.CudaCtxManager.get_ctx()
    width, height = manifest['width'], manifest['height']
    scenes = manifest['scenes']
    image_cache = {}

    def image(index):
        if index not in image_cache:
            shot = scenes[index]
            if hashlib.sha256(Path(shot['image']).read_bytes()).hexdigest() != shot['sha256']:
                raise ValueError('Prepared image changed before GPU loading')
            value = ovni.load_image(shot['image'], preserve_alpha=False)
            if value.shape != (height, width, 3):
                raise ValueError('Prepared image has unexpected dimensions')
            image_cache[index] = value
        return image_cache[index]

    def draw(index, frame):
        shot = scenes[index]
        zoom, tx, ty = camera(shot['motion'], frame, shot['motion_frames'],
                              manifest['motion_strength'], width, height)
        return scale_translate(image(index), zoom, tx, ty, width, height)

    total = sum(s['frames'] for s in scenes)

    def frames():
        done = 0
        for index, shot in enumerate(scenes):
            for local in range(shot['frames']):
                rgb = draw(index, local)
                if local < shot['fade_frames']:
                    previous = draw(index - 1, scenes[index - 1]['frames'] + local)
                    rgb = linear_blend(previous, rgb, fade_weight(local, shot['fade_frames']))
                nv12 = rgb_to_nv12(rgb)
                # The NVC encoder owns another stream: finish kernels before it reads.
                cp.cuda.get_current_stream().synchronize()
                yield nv12
                done += 1
                if done % manifest['fps'] == 0 or done == total:
                    save(manifest['progress'], {'frames': done, 'total': total}, required=False)
            # Hold only the current/previous image, independent of episode length.
            image_cache.pop(index - 1, None)
        cp.cuda.get_current_stream().synchronize()

    with Path(manifest['raw_output']).open('wb') as output:
        for packet in ovni.encode(frames(), width, height, manifest['fps'],
                                  bitrate=manifest['bitrate'], preset=manifest['preset']):
            output.write(packet)
    save(manifest['result'], {'backend': 'ovni', 'frames': total,
                             'seconds': time.perf_counter() - started,
                             'gpu': cp.cuda.runtime.getDeviceProperties(0)['name'].decode(),
                             'publication_ready': False})


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
