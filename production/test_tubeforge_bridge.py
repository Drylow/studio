"""Provider/cache and renderer contract tests without network calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tubeforge_bridge as bridge


class BridgeTests(unittest.TestCase):
    def test_voice_cache_preserves_authored_offsets(self):
        text = 'Morning begins by the river. ' * 9
        with tempfile.TemporaryDirectory() as directory:
            job = {'text': text, 'settings': {'voice_id': 'existing', 'speed': 1, 'language': 'en'},
                   'workdir': directory, 'output': str(Path(directory) / 'voice.mp3')}
            def synthesize(text, destination, **kwargs):
                self.assertEqual(kwargs['provider'], 'algrow')
                Path(destination).write_bytes(b'audio fixture')
                return {'words': [{'w': w, 's': i * .2, 'e': (i + 1) * .2}
                                  for i, w in enumerate(text.split())]}
            with patch.object(bridge.tts, 'synthesize', side_effect=synthesize) as provider, \
                    patch.object(bridge.media, 'duration', return_value=10):
                first, second = bridge.voice(job), bridge.voice(job)
                self.assertEqual(provider.call_count, 1)
                self.assertEqual(first, second)
                for word in first['words']:
                    self.assertEqual(text[word['c0']:word['c1']], word['w'])
                cached = next(Path(directory).glob('algrow-*.mp3'))
                cached.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'changed'):
                    bridge.voice(job)

    def test_short_excerpt_never_calls_provider(self):
        with patch.object(bridge.tts, 'synthesize') as provider:
            with self.assertRaisesRegex(ValueError, '200'):
                bridge.voice({'text': 'Too short.', 'settings': {}})
            provider.assert_not_called()

    def test_render_rejects_changed_audio(self):
        with patch.object(bridge.media, 'duration', return_value=11), \
                patch.object(bridge.render_ovni, 'render_video') as renderer:
            with self.assertRaisesRegex(ValueError, 'duration changed'):
                bridge.render({'voice': 'existing.mp3', 'duration': 10})
            renderer.assert_not_called()

    def test_render_forwards_clock_and_no_overlays(self):
        job = {'voice': 'existing.mp3', 'duration': 10, 'workdir': 'cache', 'scenes': [{'start': 0}],
               'output': 'final.mp4', 'width': 1920, 'height': 1080, 'fps': 24, 'motion_strength': .12,
               'cancel': 'absent-test-cancel'}
        with patch.object(bridge.media, 'duration', return_value=10), \
                patch.object(bridge.render_ovni, 'render_video', return_value={'video_frames': 240}) as renderer:
            self.assertEqual(bridge.render(job)['video_frames'], 240)
            options = renderer.call_args.kwargs
            self.assertEqual(options['fps'], 24)
            self.assertEqual(options['tail'], 0)
            self.assertEqual(options['captions'], {'mode': 'none'})
            self.assertFalse(options['cancelled']())


if __name__ == '__main__':
    unittest.main()
