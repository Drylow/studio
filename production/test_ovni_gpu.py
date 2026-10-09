"""Opt-in actual GPU/mux integration test: OVNI_GPU_TESTS=1."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from PIL import Image
from services import media, render_ovni


@unittest.skipUnless(os.environ.get('OVNI_GPU_TESTS') == '1', 'Opt-in NVIDIA integration test')
class GPUIntegrationTests(unittest.TestCase):
    def test_real_frame_clock_blend_colour_audio_and_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            scenes = []
            for index, color in enumerate(('red', 'blue')):
                image = root / f'{index}.png'
                Image.new('RGB', (320, 180), color).save(image)
                scenes.append({'start': index * 1.25, 'image': str(image), 'motion': 'none'})
            audio, output = root / 'voice.wav', root / 'test.mp4'
            media.run(['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', '3', str(audio)])
            options = dict(width=320, height=180, fps=30, transition_dur=0.2, tail=0, normalize=False)
            result = render_ovni.render_video(root / 'work', scenes, str(audio), str(output), **options)
            self.assertEqual(result['video_frames'], 90)
            self.assertFalse(result['picture_cache_reused'])
            self.assertTrue(result['qa_pending'])
            measured = subprocess.run([shutil.which('ffprobe'), '-v', 'error', '-count_frames',
                                       '-show_streams', '-of', 'json', str(output)],
                                      capture_output=True, text=True, check=True)
            streams = json.loads(measured.stdout)['streams']
            video = next(s for s in streams if s['codec_type'] == 'video')
            self.assertEqual(int(video['nb_read_frames']), 90)
            self.assertEqual(video['color_space'], 'bt709')
            self.assertEqual(video['color_range'], 'tv')
            self.assertTrue(any(s['codec_type'] == 'audio' for s in streams))
            for frame, expected in ((38, (255, 0, 0)), (41, (128, 0, 128)), (44, (0, 0, 255))):
                decoded = subprocess.run([media.ffmpeg_bin(), '-v', 'error', '-i', str(output),
                                          '-vf', f'select=eq(n\\,{frame})', '-frames:v', '1',
                                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'],
                                         capture_output=True, check=True)
                with Image.frombytes('RGB', (320, 180), decoded.stdout) as image:
                    actual = image.getpixel((160, 90))
                self.assertTrue(all(abs(a - e) <= 5 for a, e in zip(actual, expected)), (frame, actual, expected))
            again = render_ovni.render_video(root / 'work', scenes, str(audio), str(output), **options)
            self.assertTrue(again['picture_cache_reused'])
            stop = {'requested': False}

            def progress(fraction, message):
                if message == 'OVNI GPU rendering':
                    stop['requested'] = True

            with self.assertRaises(media.Cancelled):
                render_ovni.render_video(root / 'cancel', scenes, str(audio), str(root / 'cancelled.mp4'),
                                         progress=progress, cancelled=lambda: stop['requested'], **options)
            self.assertFalse((root / 'cancelled.mp4').exists())


if __name__ == '__main__':
    unittest.main()
