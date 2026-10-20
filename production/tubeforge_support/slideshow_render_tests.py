"""Small real-media check of timing, complete framing and centered dissolves."""
import json
from pathlib import Path
import subprocess
import tempfile
import wave

from PIL import Image, ImageDraw

from slideshow_render import render


def check_long_dissolves_and_outro():
    """The full requested mix must survive without shortening narration."""
    with tempfile.TemporaryDirectory(prefix='slideshow-long-check-') as folder:
        root = Path(folder)
        colors = [(224, 32, 32), (32, 32, 224), (32, 224, 32)]
        for i, color in enumerate(colors):
            Image.new('RGB', (160, 90), color).save(root / f'{i}.png')
        with wave.open(str(root / 'voice.wav'), 'wb') as wav:
            wav.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\0\0' * 8000 * 18)
        result = render({'voice': str(root / 'voice.wav'), 'out': str(root / 'out.mp4'),
                         'duration': 18, 'width': 160, 'height': 90, 'fps': 24,
                         'transition_seconds': 3, 'strict_transition_seconds': True,
                         'outro_fade_seconds': 5,
                         'scenes': [{'image': str(root / f'{i}.png'), 'start': i * 6,
                                     'end': (i + 1) * 6} for i in range(3)]})
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(root / 'out.mp4'),
                              '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-threads', '1', '-'],
                             capture_output=True, check=True).stdout
        stride = 160 * 90 * 3
        assert len(raw) == stride * 432
        for frame in range(432):
            if frame < 108:
                expected = colors[0]
            elif frame < 180:
                alpha = (frame - 108 + 1) / 73
                expected = [a * (1 - alpha) + b * alpha for a, b in zip(colors[0], colors[1])]
            elif frame < 252:
                expected = colors[1]
            elif frame < 324:
                alpha = (frame - 252 + 1) / 73
                expected = [a * (1 - alpha) + b * alpha for a, b in zip(colors[1], colors[2])]
            else:
                expected = colors[2]
            if frame >= 312:
                expected = [c * max(0, 1 - (frame - 312) / 119) for c in expected]
            offset = frame * stride + (45 * 160 + 80) * 3
            actual = raw[offset:offset + 3]
            assert max(abs(a - b) for a, b in zip(actual, expected)) < 9, (frame, actual, expected)
        assert max(actual) < 3
        assert result['transition_frame_counts'] == [72, 72]
        assert result['outro_fade_frames'] == 120 and result['frames'] == 432
        print(json.dumps({'long_fades_passed': True, 'frames_checked': 432,
                          'transition_frames': [72, 72], 'outro_frames': 120,
                          'final_frame_black': True, 'duration': 18}))


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


def check_intro_without_audio_delay():
    """Opening and ending fades affect pixels, never the narration clock."""
    with tempfile.TemporaryDirectory(prefix='slideshow-intro-check-') as folder:
        root = Path(folder)
        color = (210, 170, 90)
        Image.new('RGB', (160, 90), color).save(root / 'still.png')
        with wave.open(str(root / 'voice.wav'), 'wb') as wav:
            wav.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            # An immediate non-silent signal exposes an accidental audio fade/delay.
            import math
            import struct
            wav.writeframes(b''.join(struct.pack('<h', round(5000 * math.sin(i * .21)))
                                     for i in range(8000 * 6)))
        result = render({'voice': str(root / 'voice.wav'), 'out': str(root / 'out.mp4'),
                         'duration': 6, 'width': 160, 'height': 90, 'fps': 24,
                         'intro_fade_seconds': 1, 'outro_fade_seconds': 2,
                         'scenes': [{'image': str(root / 'still.png'), 'start': 0, 'end': 6}]})
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(root / 'out.mp4'),
                              '-threads', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'],
                             capture_output=True, check=True).stdout
        stride = 160 * 90 * 3
        assert len(raw) == stride * 144
        for n in range(144):
            gain = min(1, n / 23) * (max(0, 1 - (n - 96) / 47) if n >= 96 else 1)
            offset = n * stride + (45 * 160 + 80) * 3
            assert max(abs(a - b * gain) for a, b in zip(raw[offset:offset + 3], color)) < 9
        signal = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(root / 'out.mp4'),
                                 '-vn', '-ac', '1', '-ar', '8000', '-f', 's16le', '-'],
                                capture_output=True, check=True).stdout
        values = struct.unpack('<' + 'h' * (len(signal) // 2), signal)
        expected = [round(5000 * math.sin(i * .21)) for i in range(8000)]
        error = sum(abs(a - b) for a, b in zip(values[:8000], expected)) / 8000
        assert error < 500, error
        assert result['intro_fade_frames'] == 24 and result['outro_fade_frames'] == 48
        assert result['frames'] == 144
        print(json.dumps({'intro_and_outro_passed': True, 'frames_checked': 144,
                          'intro_frames': 24, 'outro_frames': 48, 'audio_start_error': error}))


if __name__ == '__main__':
    main()
    check_long_dissolves_and_outro()
    check_intro_without_audio_delay()
