import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location('review_excerpt', Path(__file__).with_name('review_excerpt.py'))
excerpt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(excerpt)


class ExcerptContractTests(unittest.TestCase):
    def test_full_episode_cannot_enter_excerpt_preparation(self):
        with self.assertRaises(AssertionError):
            excerpt.prepare({'phase': 'complete-episode'})

    def test_repeated_selection_cannot_pad_excerpt(self):
        with self.assertRaises(AssertionError):
            excerpt.prepare({'phase': 'review-excerpt-NOT-complete-episode', 'selection': ['one', 'one']})

    def test_render_rejects_missing_manual_notes(self):
        manifest = {'workdir': 'work', 'phase': 'review-excerpt-NOT-complete-episode',
                    'source_audio': 'audio', 'selection': ['one']}
        plan = {'phase': manifest['phase'], 'source_audio_sha256': 'sha', 'shots': [{'id': 'one'}]}
        approval = {'one': {'accepted': True, 'notes': ''}}
        with patch.object(excerpt.ep, 'read', side_effect=[plan, approval]), \
             patch.object(excerpt.ep, 'digest', return_value='sha'), \
             patch.object(excerpt.subprocess, 'run') as process:
            with self.assertRaises(AssertionError):
                excerpt.render(manifest)
            process.assert_not_called()

    def test_render_rejects_changed_source_before_encoding(self):
        manifest = {'workdir': 'work', 'phase': 'review-excerpt-NOT-complete-episode',
                    'source_audio': 'audio', 'selection': ['one']}
        shot = {'id': 'one', 'image': 'frame', 'sha256': 'sha', 'source': 'source', 'source_sha256': 'old'}
        plan = {'phase': manifest['phase'], 'source_audio_sha256': 'sha', 'shots': [shot]}
        approval = {'one': {'accepted': True, 'notes': 'Viewed frame', 'sha256': 'sha'}}
        with patch.object(excerpt.ep, 'read', side_effect=[plan, approval]), \
             patch.object(excerpt.ep, 'digest', return_value='sha'), \
             patch.object(excerpt.subprocess, 'run') as process:
            with self.assertRaises(AssertionError):
                excerpt.render(manifest)
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
