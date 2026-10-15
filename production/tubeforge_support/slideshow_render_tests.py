"""Small real-media check of timing, complete framing and centered dissolves."""
import json
from pathlib import Path
import subprocess
import tempfile
import wave

from PIL import Image, ImageDraw

from slideshow_render import render


def main():
    with tempfile.TemporaryDirectory(prefix='slideshow-check-') as folder:
        root = Path(folder)
        colors = [(230, 30, 30), (30, 30, 230), (30, 230, 30)]
        for i, color in enumerate(colors):
            picture = Image.new('RGB', (160, 90), color)
            draw = ImageDraw.Draw(picture)
            for x, y in [(0, 0), (152, 0), (0, 82), (152, 82)]:
                draw.rectangle((x, y, x + 7, y + 7), fill='white')
            picture.save(root / f'{i}.png')
        with wave.open(str(root / 'voice.wav'), 'wb') as wav:
            wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\0\0' * 24000 * 6)
        result = render({'voice': str(root / 'voice.wav'), 'out': str(root / 'out.mp4'),
                         'duration': 6, 'width': 160, 'height': 90, 'fps': 24,
                         'transition_seconds': .25,
                         'scenes': [{'image': str(root / f'{i}.png'), 'start': i * 2,
                                     'end': (i + 1) * 2} for i in range(3)]})
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-threads', '1', '-i', str(root / 'out.mp4'),
                              '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-threads', '1', '-'],
                             capture_output=True, check=True).stdout
        stride = 160 * 90 * 3
        assert len(raw) == stride * 144
        def pixel(frame):
            offset = frame * stride + (45 * 160 + 80) * 3
            return tuple(raw[offset:offset + 3])
        for a, b in [(0, 44), (51, 92), (99, 143)]:
            assert max(abs(x-y)for x,y in zip(pixel(a),pixel(b))) <= 2
        # Six blended frames, straddling the original two-second boundary.
        red = [pixel(f)[0] for f in range(44, 52)]
        blue = [pixel(f)[2] for f in range(44, 52)]
        assert all(a > b for a,b in zip(red,red[1:])), red
        assert all(a < b for a,b in zip(blue,blue[1:])), blue
        assert result['frames'] == 144 and result['transition_frame_counts'] == [6, 6]
        for x,y in [(4,4),(155,4),(4,85),(155,85)]:
            offset=(y*160+x)*3
            assert min(raw[offset:offset+3])>220,'Complete input corners must survive; no zoom margin'
        print(json.dumps({'passed': True, 'frames': 144, 'duration': result['duration'],
                          'checks': ['static holds', 'complete framing/corners', 'centered six-frame fades', 'narration duration']}))


if __name__ == '__main__':
    main()
