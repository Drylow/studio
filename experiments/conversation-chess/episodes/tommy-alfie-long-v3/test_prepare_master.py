"""Actual short media regressions for the exact 30 fps / 48 kHz master clock."""
import contextlib
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('peaky_prepare_master', HERE / 'prepare-master.py')
HELPER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HELPER)


@unittest.skipUnless(shutil.which(HELPER.FFMPEG) and shutil.which(HELPER.FFPROBE), 'Local FFmpeg/FFprobe required')
class ActualMediaClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='peaky-master-clock-')
        cls.out = Path(cls.temporary.name)
        (cls.out / 'parts').mkdir()
        for bold, target in ((False, 'chapter-regular.ttf'), (True, 'chapter-bold.ttf')):
            shutil.copyfile(HELPER.find_font(None, bold), cls.out / target)
        cls.source = cls.out / 'native-25fps.mkv'
        subprocess.run([HELPER.FFMPEG, '-nostdin', '-v', 'error', '-n',
                        '-f', 'lavfi', '-i', 'color=c=navy:s=1280x720:r=25:d=7',
                        '-f', 'lavfi', '-i', 'sine=frequency=330:sample_rate=48000:duration=7',
                        '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-threads', '2', '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', '-ac', '2',
                        str(cls.source)], check=True, capture_output=True)
        cls.count = 176
        # Native 25 fps input, seek on a 30 fps boundary, retain right through
        # EOF. This is the fractional 5.866667 s interval that exposed -t loss.
        cls.row = {'kind': 'source', 'id': 'source-at-eof', 'source_id': 'fixture',
                   'source_in': 34 / 30, 'duration_frames': cls.count}
        with contextlib.redirect_stdout(io.StringIO()):
            cls.part = HELPER.encode_part(cls.row, 0, cls.out, {'fixture': {'path': cls.source}})

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_fractional_source_cut_at_eof_keeps_all_pcm_samples_and_pts(self):
        path = Path(self.part['path'])
        decoded = HELPER.probe(path, frames=True)
        picture = [f for f in decoded['frames'] if f['media_type'] == 'video']
        audio = [f for f in decoded['frames'] if f['media_type'] == 'audio']
        self.assertEqual(len(picture), 176)
        self.assertEqual(sum(f['nb_samples'] for f in audio), 176 * 1600)
        self.assertAlmostEqual(float(picture[0]['best_effort_timestamp_time']), 0, delta=.0011)
        self.assertAlmostEqual(float(picture[-1]['best_effort_timestamp_time']), 175 / 30, delta=.0011)
        cursor = 0
        for frame in audio:
            self.assertAlmostEqual(float(frame['best_effort_timestamp_time']), cursor / 48000, delta=.0011)
            cursor += frame['nb_samples']
        pcm = subprocess.run([HELPER.FFMPEG, '-nostdin', '-v', 'error', '-i', str(path),
                              '-map', '0:a:0', '-c:a', 'pcm_s16le', '-f', 's16le', '-'],
                             check=True, capture_output=True).stdout
        self.assertEqual(len(pcm), 176 * 1600 * 2 * 2)
        self.assertTrue(HELPER.verify_intermediate(path, 176)['decoded_counts']['continuous_timestamps'])

    def test_finite_chapter_and_concat_keep_both_clocks_exact(self):
        row = {'kind': 'chapter_card', 'id': 'chapter', 'title': 'Clock regression', 'duration_frames': 31}
        with contextlib.redirect_stdout(io.StringIO()):
            part = HELPER.encode_part(row, 1, self.out, {})
        self.assertEqual(part['probe']['decoded_counts']['audio_samples_per_channel'], 31 * 1600)
        concat = self.out / 'parts.ffconcat'
        concat.write_text('ffconcat version 1.0\n'
                          f"file 'parts/part-00.mkv'\nduration {176 / 30:.9f}\n"
                          f"file 'parts/part-01.mkv'\nduration {31 / 30:.9f}\n", encoding='utf-8')
        master = self.out / 'short-master.mkv'
        HELPER.concatenate_parts(concat, master, self.out)
        measured = HELPER.verify_intermediate(master, 176 + 31)
        self.assertEqual(measured['decoded_counts']['audio_samples_per_channel'], 207 * 1600)

    def test_incomplete_pcm_is_refused_even_with_all_video_frames(self):
        damaged = self.out / 'truncated-pcm.mkv'
        subprocess.run([HELPER.FFMPEG, '-nostdin', '-v', 'error', '-n', '-i', self.part['path'],
                        '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'copy', '-r:v', '30',
                        '-af', f'atrim=end_sample={176 * 1600 - 704}', '-c:a', 'pcm_s16le',
                        '-avoid_negative_ts', 'disabled', str(damaged)], check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, 'picture/audio sample totals'):
            HELPER.verify_intermediate(damaged, 176)


if __name__ == '__main__':
    unittest.main()
