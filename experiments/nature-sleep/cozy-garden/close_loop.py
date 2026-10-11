"""Close the encoded master without a periodic texture change from quantisation."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'output/nature-sleep/garden-production'

def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()

def main():
    receipt = json.loads((OUT / 'render-receipt.json').read_text())
    target = OUT / 'loop.mp4'
    master = OUT / 'loop-master.mp4'
    if not master.exists():
        assert sha(target) == receipt['sha256']
        target.rename(master)
    assert sha(master) == receipt['sha256']
    temporary = OUT / 'loop-closed.partial.mp4'
    # Start at second one. Blend the last second into the first second,
    # ending one normal frame before the next cycle's second-one frame.
    filters = ('[0:v]split=3[m][t][h];'
               '[m]trim=start=1:end=59,setpts=PTS-STARTPTS[main];'
               '[t]trim=start=59:end=60,setpts=PTS-STARTPTS[tail];'
               '[h]trim=start=0:end=1,setpts=PTS-STARTPTS[head];'
               "[tail][head]blend=all_expr='round(A*(1-min(T*30/29,1))+B*min(T*30/29,1))':shortest=1[c];"
               '[main][c]concat=n=2:v=1:a=0[out]')
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-nostdin',
               '-threads', '2', '-i', str(master), '-filter_complex_threads', '1',
               '-filter_complex', filters, '-map', '[out]', '-an', '-r', '30',
               '-frames:v', '1770', '-c:v', 'libx264', '-preset', 'fast', '-crf', '0',
               '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
               '-y', str(temporary)]
    subprocess.run(command, check=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error',
        '-show_streams', '-show_format', '-of', 'json', str(temporary)]))
    stream = probe['streams'][0]
    assert int(stream['nb_frames']) == 1770
    assert abs(float(probe['format']['duration']) - 59) < .01
    assert stream['avg_frame_rate'] == '30/1'
    temporary.replace(target)
    result = {'master_sha256': receipt['sha256'], 'sha256': sha(target),
              'duration': 59, 'frames': 1770, 'fps': 30,
              'lossless_intermediate': True, 'cyclic_crossfade_seconds': 1,
              'source_intervals': 'main 1..59; blend tail 59..60 into head 0..1, rounded and reaching head exactly on last frame',
              'command': command, 'bytes': target.stat().st_size}
    (OUT / 'loop-transform.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
