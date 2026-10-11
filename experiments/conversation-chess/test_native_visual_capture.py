import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


module_spec = importlib.util.spec_from_file_location(
    'native_capture', Path(__file__).with_name('check-native-export.py'))
native = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(native)


class ChapterCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.data = {
            'fps': 30, 'duration_frames': 1170,
            'original_source': str(self.directory / 'source.mkv'),
            'segments': [
                {'kind': 'intro', 'start_frame': 0, 'end_frame': 480},
                {'kind': 'source', 'start_frame': 480, 'end_frame': 540,
                 'source_in': 0, 'source_out': 2},
                {'kind': 'analysis', 'start_frame': 540, 'end_frame': 750,
                 'comment': 'A complete comment.', 'rating': 'best', 'speaker': 'white',
                 'score_text': '0.0'},
                {'kind': 'source', 'start_frame': 750, 'end_frame': 810,
                 'source_in': 2, 'source_out': 4},
                {'kind': 'outro', 'start_frame': 810, 'end_frame': 1170},
            ]}
        self.schema = {'bubble_delay_seconds': .5, 'typewriter_cps': 30}
        self.card = {'kind': 'chapter_card', 'title': 'A disclosed omission',
                     'master_in_frames': 30, 'duration_frames': 30}

    def plan(self, master):
        (self.directory / 'source-master-manifest.json').write_text(json.dumps(master))
        return native.visual_capture_plan(self.data, self.schema, self.directory / 'qa')

    def test_nested_and_direct_cards_map_to_identical_real_frame(self):
        direct = self.plan({'source_map': [self.card]})
        nested = self.plan({'source_edit': {'source_map': [self.card]}})
        self.assertEqual(direct, nested)
        chapters = [s for s in nested['captures'] if s['group'] == 'chapters']
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0]['frame'], 525)
        self.assertFalse(nested['finished_render_visual_reviewed'])

    def test_direct_map_keeps_precedence_over_nested_legacy_metadata(self):
        plan = self.plan({'source_map': [], 'source_edit': {'source_map': [self.card]}})
        self.assertNotIn('chapters', plan['group_counts'])

    def test_unretained_card_raises_instead_of_silently_skipping_review(self):
        card = copy.deepcopy(self.card)
        card['master_in_frames'] = 120
        with self.assertRaisesRegex(ValueError, 'not retained'):
            self.plan({'source_edit': {'source_map': [card]}})


if __name__ == '__main__':
    unittest.main()
