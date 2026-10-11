"""Validate exact native parent and audio-finished child using actual short media."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave

import numpy as np

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('native_check', HERE / 'check-native-export.py')
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)
FINISH_SPEC = importlib.util.spec_from_file_location('audio_finish', HERE / 'finish-dialogue-audio.py')
FINISH = importlib.util.module_from_spec(FINISH_SPEC)
FINISH_SPEC.loader.exec_module(FINISH)


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
class NativeAudioFinishingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-finish-test-', dir='/tmp')
        cls.folder = Path(cls.directory.name)
        cls.parent = cls.folder / 'native.mp4'
        cls.output = cls.folder / 'finished.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=blue:s=320x180:r=30:d=2',
            '-f', 'lavfi', '-i', 'sine=frequency=330:sample_rate=48000:duration=2', '-c:v', 'libx264',
            '-threads', '1', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ac', '2', str(cls.parent)], check=True)
        filter_value, sample_ranges = FINISH.source_gain_filter([(.5, 1.5)], 5.5)
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(cls.parent), '-map', '0:v:0', '-map', '0:a:0',
            '-c:v', 'copy', '-af', filter_value,
            '-c:a', 'aac', '-b:a', '192k', str(cls.output)], check=True)
        cls.export = cls.folder / 'native.json'
        cls.export.write_text(json.dumps({'export_completed': True, 'final_video': str(cls.parent),
                                         'output_sha256': HELPER.sha256(cls.parent)}))
        cls.data = {'fps': 30, 'segments': [
            {'kind': 'intro', 'start_frame': 0, 'end_frame': 15},
            {'kind': 'source', 'start_frame': 15, 'end_frame': 45},
            {'kind': 'outro', 'start_frame': 45, 'end_frame': 60}]}
        cls.receipt = {'parent_video': str(cls.parent), 'parent_sha256': HELPER.sha256(cls.parent),
            'output_video': str(cls.output), 'sha256': HELPER.sha256(cls.output),
            'bytes': cls.output.stat().st_size, 'source_audio_gain_db': 5.5,
            'source_output_ranges': [[.5, 1.5]], 'intro_analysis_outro_audio_gain_db': 0,
            'source_output_sample_ranges': sample_ranges, 'source_interval_policy': 'half-open-sample-index',
            'audio_sample_rate': 48000,
            'picture_stream_unchanged': True, 'picture_stream_sha256': HELPER.picture_hash(cls.parent),
            'full_decode_passed': True, 'preserve_grading_music': True, 'human_audio_listening': False}
        cls.finish = cls.folder / 'finish.json'

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.finish.write_text(json.dumps(self.receipt))

    def check(self):
        return HELPER.validate_native_provenance(self.output, self.export, self.data, self.finish)

    def test_actual_copy_video_child_has_distinct_container_sha_and_preserved_picture(self):
        before = self.export.read_bytes()
        result = self.check()
        self.assertNotEqual(result['output_sha256'], result['native_output_sha256'])
        self.assertEqual(result['source_audio_gain_db'], 5.5)
        self.assertFalse(result['audio_finishing']['human_audio_listening'])
        self.assertEqual(self.export.read_bytes(), before)
        direct = HELPER.validate_native_provenance(self.parent, self.export, self.data)
        self.assertIsNone(direct['audio_finishing'])

    def test_child_cannot_be_passed_off_as_direct_native_export(self):
        with self.assertRaisesRegex(ValueError, 'provide audio_finishing_receipt'):
            HELPER.validate_native_provenance(self.output, self.export, self.data)

    def test_finite_gain_native_parent_and_source_ranges_are_required(self):
        for change, message in [({'source_audio_gain_db': float('nan')}, 'finite'),
                                ({'parent_sha256': '0'*64}, 'exact native parent'),
                                ({'source_output_ranges': [[0, 2]]}, 'source ranges'),
                                ({'intro_analysis_outro_audio_gain_db': 1}, 'preserved grade/music')]:
            with self.subTest(change=change):
                self.finish.write_text(json.dumps({**self.receipt, **change}))
                with self.assertRaisesRegex(ValueError, message):
                    self.check()

    def test_unchanged_boolean_cannot_hide_replaced_picture_stream(self):
        replaced = self.folder / 'replaced.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:s=320x180:r=30:d=2',
            '-i', str(self.output), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-threads', '1',
            '-pix_fmt', 'yuv420p', '-c:a', 'copy', str(replaced)], check=True)
        receipt = copy.deepcopy(self.receipt)
        receipt.update(output_video=str(replaced), sha256=HELPER.sha256(replaced), bytes=replaced.stat().st_size)
        self.finish.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'changed the native picture stream'):
            HELPER.validate_native_provenance(replaced, self.export, self.data, self.finish)

    def test_sample_gain_does_not_boost_the_following_grade_at_an_aac_frame_boundary(self):
        # Frame17 at 30fps is sample27200: an AAC1024 frame straddles that boundary.
        rate, first, last = 48000, 6400, 27200
        samples = np.arange(rate)
        values = np.column_stack((1200 + 800*np.sin(samples*.09),
                                  -1500 + 700*np.sin(samples*.13))).astype('<i2')
        wav = self.folder / 'boundary-stereo.wav'
        with wave.open(str(wav), 'wb') as audio:
            audio.setnchannels(2); audio.setsampwidth(2); audio.setframerate(rate)
            audio.writeframes(values.tobytes())
        gain_db = 20*np.log10(2)
        audio_filter, ranges = FINISH.source_gain_filter([(first/rate, last/rate)], float(gain_db))
        result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(wav), '-af', audio_filter,
            '-c:a', 'pcm_f32le', '-f', 'f32le', '-'], capture_output=True, check=True)
        actual = np.frombuffer(result.stdout, dtype='<f4').reshape(-1, 2)
        original = values.astype(np.float32)/32768
        expected = original.copy(); expected[first:last] *= 2
        self.assertEqual(ranges, [(first, last)])
        self.assertEqual(len(actual), rate)
        np.testing.assert_allclose(actual, expected, atol=1e-7, rtol=1e-6)
        np.testing.assert_allclose(actual[last:last+1024], original[last:last+1024], atol=1e-7)

    def test_sample_gain_refuses_nonfinite_and_overlapping_ranges(self):
        for ranges in [[(0, float('inf'))], [(0, 1), (.5, 2)], [(1, 1)]]:
            with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                FINISH.source_gain_filter(ranges, 5.5)


if __name__ == '__main__':
    unittest.main()
