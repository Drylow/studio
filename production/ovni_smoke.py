"""Isolated OVNI installation check and benchmark; never a delivery render."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import time


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def compile_kernels(source):
    os.environ['CUPY_COMPILE_WITH_PTX'] = '1'
    import cupy as cp
    from cupy.cuda.compiler import _NVRTCProgram

    directory = source / 'ovni/kernels/src'
    spec = importlib.util.find_spec('ovni')
    target = Path(spec.origin).parent / 'kernels/compiled/all_kernels.ptx'
    props = cp.cuda.runtime.getDeviceProperties(0)
    arch = f"{props['major']}{props['minor']}"
    # NVRTC compiles the same upstream kernels without a system MSVC install.
    program = _NVRTCProgram(
        (directory / 'all_kernels.cu').read_text(encoding='utf-8'), 'ovni.cu',
        headers=(b'typedef unsigned int uint32_t;',), include_names=(b'stdint.h',))
    code, _ = program.compile((f'-I{directory.resolve()}', '--std=c++11',
                               f'-arch=compute_{arch}'))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(code)
    receipt = {'backend': 'NVRTC', 'architecture': arch, 'ptx_sha256': digest(target),
               'virtual_header': 'stdint.h: typedef unsigned int uint32_t; (only upstream use)',
               'source_sha256': {p.name: digest(p) for p in directory.glob('*.cu')}}
    save(target.with_suffix('.build.json'), receipt)
    print(json.dumps(receipt, indent=2), flush=True)


def selected_shots(timeline, approval, seconds):
    shots = []
    cursor = 0.0
    for shot in timeline['shots']:
        if shot['start'] >= seconds:
            break
        assert abs(shot['start'] - cursor) < 0.001, 'Timeline gap'
        assert 0 < shot['end'] - shot['start'] <= 6, 'Cadence exceeds six seconds'
        assert digest(shot['image']) == shot['sha256'], 'Image changed after review'
        decision = approval[shot['id']]
        assert decision['accepted'] and decision['sha256'] == shot['sha256']
        shots.append({**shot, 'end': min(shot['end'], seconds)})
        cursor = shots[-1]['end']
    assert abs(cursor - seconds) < 0.001, 'Not enough approved footage'
    return shots


def benchmark(args):
    import cupy as cp
    import cv2
    import numpy as np
    import ovni
    from ovni.ops import rgb_to_nv12, scale_translate

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / 'benchmark.json'
    assert not result_path.exists(), 'Use a fresh benchmark output directory'
    timeline = json.loads(Path(args.timeline).read_text(encoding='utf-8'))
    approval = json.loads(Path(args.approval).read_text(encoding='utf-8'))
    shots = selected_shots(timeline, approval, args.seconds)
    frames = math.ceil(args.seconds * 30)
    assert frames / 30 == args.seconds, 'Benchmark must end on a frame boundary'
    ovni.CudaCtxManager.get_ctx()
    name = cp.cuda.runtime.getDeviceProperties(0)['name'].decode()
    started = time.perf_counter()
    images = []
    for shot in shots:
        image = ovni.load_image(shot['image'], preserve_alpha=False)
        assert image.shape == (1080, 1920, 3), image.shape
        images.append(image)
    cp.cuda.get_current_stream().synchronize()
    load_seconds = time.perf_counter() - started

    def frame_generator():
        index = 0
        for number in range(frames):
            t = number / 30
            while index + 1 < len(shots) and t >= shots[index]['end']:
                index += 1
            shot = shots[index]
            progress = (t - shot['start']) / (shot['end'] - shot['start'])
            zoom = 1 + 0.025 * progress
            rgb = scale_translate(images[index], zoom, -(zoom - 1) * 960,
                                  -(zoom - 1) * 540, 1920, 1080)
            nv12 = rgb_to_nv12(rgb)
            # OVNI's encoder uses another CUDA stream; finish image operations first.
            cp.cuda.get_current_stream().synchronize()
            yield nv12

    raw = output / 'ovni.h264'
    started = time.perf_counter()
    with raw.open('wb') as handle:
        for packet in ovni.encode(frame_generator(), 1920, 1080, 30, bitrate='8M', preset='P3'):
            handle.write(packet)
    encode_seconds = time.perf_counter() - started
    video = output / 'OVNI-TECHNICAL-TEST-NOT-PUBLISHABLE.mp4'
    started = time.perf_counter()
    subprocess.run([args.ffmpeg, '-v', 'error', '-n', '-r', '30', '-i', str(raw),
                    '-i', args.audio, '-t', str(args.seconds), '-map', '0:v:0', '-map', '1:a:0',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                    str(video)], check=True)
    mux_seconds = time.perf_counter() - started
    capture = cv2.VideoCapture(str(video))
    assert capture.isOpened()
    assert int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) == frames
    assert abs(capture.get(cv2.CAP_PROP_FPS) - 30) < 0.01
    comparisons = []
    for index, shot in enumerate(shots):
        frame_number = min(frames - 1, math.ceil(shot['start'] * 30) + 1)
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, frame = capture.read()
        assert ok and frame.shape == (1080, 1920, 3)
        assert frame.std() > 15, 'Blank or corrupt output'
        reference = cv2.imread(shot['image'])
        mae = float(np.abs(frame.astype(np.float32) - reference).mean())
        assert mae < 12, f'Unexpected colour or framing error: {mae}'
        check = output / f'check-{index + 1:02}.png'
        assert cv2.imwrite(str(check), frame)
        comparisons.append({'shot': shot['id'], 'capture': str(check), 'rgb_mae': mae})
    capture.release()
    subprocess.run([args.ffmpeg, '-v', 'error', '-i', str(video), '-f', 'null', '-'], check=True)
    result = {'phase': 'technical-test-NOT-complete-episode', 'gpu': name,
              'frames': frames, 'duration': args.seconds, 'images': len(shots),
              'load_seconds': load_seconds, 'encode_seconds': encode_seconds,
              'mux_seconds': mux_seconds, 'total_seconds': load_seconds + encode_seconds + mux_seconds,
              'encode_fps': frames / encode_seconds, 'output': str(video),
              'output_sha256': digest(video), 'comparisons': comparisons,
              'visual_review_pending': True, 'publication_ready': False,
              'motion': 'Centred 2.5 percent linear zoom, hard cuts; no fades in this technical test.'}
    save(result_path, result)
    print(json.dumps(result, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    build = sub.add_parser('compile')
    build.add_argument('--source', type=Path, required=True)
    test = sub.add_parser('benchmark')
    for field in ('timeline', 'approval', 'ffmpeg', 'audio', 'output'):
        test.add_argument('--' + field, required=True)
    test.add_argument('--seconds', type=float, default=30)
    args = parser.parse_args()
    if args.action == 'compile':
        compile_kernels(args.source)
    else:
        benchmark(args)


if __name__ == '__main__':
    main()
