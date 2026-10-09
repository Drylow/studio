import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import historical_renderer
from services import media, render_ovni
from services.ovni_timeline import camera, fade_weight, frame_plan


class ClockTests(unittest.TestCase):
    def test_fades_never_shorten_voice_clock(self):
        scenes = [{'start': i * 5.2, 'motion': 'zoom_in'} for i in range(36)]
        plan = frame_plan(scenes, 190.43, 30, transition_dur=0.15)
        self.assertEqual(sum(s['frames'] for s in plan), round(190.43 * 30))
        self.assertEqual(plan[1]['start_frame'], 156)
        self.assertEqual(plan[1]['fade_frames'], 4)
        self.assertEqual(plan[0]['motion_frames'], 160)

    def test_short_shot_clamps_fade(self):
        plan = frame_plan([{'start': 0}, {'start': 1}], 1.1, 30, transition_dur=0.5)
        self.assertEqual(plan[1]['fade_frames'], 2)
        self.assertEqual(sum(s['frames'] for s in plan), 33)

    def test_cut_has_no_overlap(self):
        plan = frame_plan([{'start': 0}, {'start': 1}], 2, 30, 'cut')
        self.assertTrue(all(s['fade_frames'] == 0 and s['motion_frames'] == s['frames'] for s in plan))

    def test_invalid_clocks_rejected(self):
        for starts in ([1], [0, 0], [0, -1], [0, 2], [0, float('nan')]):
            with self.subTest(starts=starts), self.assertRaises(ValueError):
                frame_plan([{'start': s} for s in starts], 2, 30)
        for fps in (0, 29.97, float('inf')):
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                frame_plan([{'start': 0}], 1, fps)

    def test_fade_endpoints(self):
        self.assertEqual(fade_weight(0, 4), 0)
        self.assertEqual(fade_weight(2, 4), 0.5)
        self.assertEqual(fade_weight(4, 4), 1)
        self.assertEqual(fade_weight(0, 0), 1)

    def test_center_zoom_and_pan_cover_frame(self):
        self.assertEqual(camera('zoom_in', 0, 31, 0.1, 1920, 1080), (1, 0, 0))
        zoom, x, y = camera('zoom_in', 30, 31, 0.1, 1920, 1080)
        self.assertAlmostEqual(zoom, 1.1)
        self.assertAlmostEqual(x, -96)
        self.assertAlmostEqual(y, -54)
        for kind in ('pan_right', 'pan_left', 'pan_up', 'pan_down', 'zoom_in_tl', 'zoom_in_br'):
            for frame in (0, 15, 30):
                z, tx, ty = camera(kind, frame, 31, 0.1, 1920, 1080)
                self.assertLessEqual(tx, 0.000001)
                self.assertLessEqual(ty, 0.000001)
                self.assertGreaterEqual(tx + 1920 * z, 1920 - 0.000001)
                self.assertGreaterEqual(ty + 1080 * z, 1080 - 0.000001)


class BackendTests(unittest.TestCase):
    def test_all_five_channels_default_to_gpu(self):
        with patch.object(historical_renderer.render_ovni, 'render_video', return_value={'backend': 'ovni'}) as gpu:
            for channel in historical_renderer.CHANNELS:
                self.assertEqual(historical_renderer.render_video({'channel': channel}), {'backend': 'ovni'})
            self.assertEqual(gpu.call_count, 5)

    def test_other_channels_unchanged_and_explicit_studio_supported(self):
        with patch.object(historical_renderer.render, 'render_video', return_value={'path': 'x'}) as cpu:
            self.assertEqual(historical_renderer.render_video({'channel': 'other'})['backend'], 'studio')
            historical_renderer.render_video({'channel': 'edo-daily', 'render_backend': 'studio'})
            self.assertEqual(cpu.call_count, 2)

    def test_wrong_channel_and_unknown_backend_rejected(self):
        for value in ({'channel': 'other', 'render_backend': 'ovni'}, {'render_backend': 'unknown'}):
            with self.assertRaises(ValueError):
                historical_renderer.render_video(value)

    def test_gpu_failure_does_not_switch_to_cpu(self):
        with patch.object(historical_renderer.render_ovni, 'render_video', side_effect=media.MediaError('failed')), \
             patch.object(historical_renderer.render, 'render_video') as cpu:
            with self.assertRaises(media.MediaError):
                historical_renderer.render_video({'channel': 'edo-daily'})
            cpu.assert_not_called()

    def test_unsupported_features_fail_before_launch(self):
        for option in ({'layout': {'mode': 'board'}}, {'captions': {'mode': 'burn'}}, {'overlays': [1]}, {'fx': [1]}):
            with patch.object(render_ovni, 'runtime') as launch:
                with self.assertRaises(media.MediaError):
                    render_ovni.render_video('work', [], 'voice', 'output', **option)
                launch.assert_not_called()

    def test_cache_requires_receipt_hash_and_clock(self):
        with tempfile.TemporaryDirectory() as folder:
            picture, receipt = Path(folder) / 'picture.mp4', Path(folder) / 'receipt.json'
            picture.write_bytes(b'video')
            self.assertFalse(render_ovni.cached_picture(picture, receipt, 60))
            receipt.write_text(json.dumps({'frames': 60, 'picture_sha256': render_ovni.digest(picture)}))
            self.assertTrue(render_ovni.cached_picture(picture, receipt, 60))
            self.assertFalse(render_ovni.cached_picture(picture, receipt, 61))
            picture.write_bytes(b'corrupted')
            self.assertFalse(render_ovni.cached_picture(picture, receipt, 60))


if __name__ == '__main__':
    unittest.main()
