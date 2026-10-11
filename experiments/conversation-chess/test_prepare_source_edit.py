"""Run with python -m unittest discover -s experiments/conversation-chess -p test_prepare_source_edit.py."""
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('source_edit', HERE / 'prepare-source-edit.py')
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


def source_meta(width=1280, height=720, duration=4):
    return {'streams': [{'codec_type': 'video', 'width': width, 'height': height,
                         'sample_aspect_ratio': '1:1'}, {'codec_type': 'audio'}],
            'format': {'duration': str(duration)}}


def fixture():
    timeline = {'schema': 'conversation-chess-clip-v1', 'white_label': 'First',
                'black_label': 'Second', 'intro_seconds': 16, 'outro_seconds': 12,
                'source_quality': {'quality_target': 1080, 'accepted_for_final': False},
                'opening': {'speaker': 'white', 'label': 'First', 'reviewed': True},
                'annotations': [{'source_at': .75, 'comment': 'First decision.', 'hold_seconds': 7},
                                {'source_at': 2.75, 'comment': 'Second decision.', 'hold_seconds': 7}]}
    edit = {'schema': 'conversation-chess-source-edit-v1', 'source_visually_reviewed': True,
            'source_dimensions': {'width': 1280, 'height': 720},
            'white_label': 'First', 'black_label': 'Second',
            'opening': {'speaker': 'white', 'label': 'First', 'reviewed': True, 'source_at': .5,
                        'evidence': 'Synthetic first speaker is retained at the beginning.'},
            'cuts': [{'in': .5, 'out': 1, 'reason': 'Retain the first synthetic red shot.'},
                     {'in': 2, 'out': 3, 'reason': 'Retain the second synthetic blue shot.'}],
            'annotations': [{'base_index': 0, 'original_at': .75},
                            {'base_index': 1, 'original_at': 2.75, 'comment': 'Edited second decision.'}]}
    return edit, timeline


def conversation_fixture():
    edit, timeline = fixture()
    timeline.update(source_in=0, source_out=4, initial_score_text='0.0', initial_control=.5)
    timeline['opening'].update(source_at=0, evidence='Reviewed original first White opening.')
    timeline['conversations'] = [
        {'source_at': 0, 'white_label': 'First', 'black_label': 'Second',
         'opening': copy.deepcopy(timeline['opening']), 'initial_score_text': '0.0', 'initial_control': .5},
        {'source_at': 2, 'white_label': 'Second', 'black_label': 'First',
         'opening': {'speaker': 'white', 'label': 'Second', 'reviewed': True,
                     'evidence': 'The second conversation starts with Second speaking.'},
         'initial_score_text': '0.0', 'initial_control': .5}]
    return edit, timeline


class AuthoredPlanTests(unittest.TestCase):
    def test_remapping_uses_retained_cuts_and_preserves_source_decisions(self):
        edit, timeline = fixture()
        original = copy.deepcopy((edit, timeline))
        planned, cuts, frames, dimensions = HELPER.plan_edit(edit, timeline, source_meta())
        self.assertEqual([a['source_at'] for a in planned['annotations']], [.25, 1.25])
        self.assertEqual([a['original_source_at'] for a in planned['annotations']], [.75, 2.75])
        self.assertEqual(planned['annotations'][1]['comment'], 'Edited second decision.')
        self.assertEqual([c['edited_in'] for c in cuts], [0, .5])
        self.assertEqual((frames, planned['source_out'], dimensions), (45, 1.5, {'width': 1280, 'height': 720}))
        self.assertEqual(planned['opening'], edit['opening'])
        self.assertNotIn('conversations', planned)
        self.assertEqual(planned['source_quality'], timeline['source_quality'])
        self.assertEqual((edit, timeline), original)

    def test_opening_is_required_even_if_base_timeline_has_one(self):
        edit, timeline = fixture()
        del edit['opening']
        with self.assertRaisesRegex(ValueError, 'own explicitly reviewed opening'):
            HELPER.plan_edit(edit, timeline, source_meta())

    def test_opening_requires_evidence_and_the_actual_retained_beginning(self):
        for change, message in [({'evidence': ''}, 'needs evidence'),
                                ({'source_at': 0}, 'first retained cut'),
                                ({'speaker': 'black'}, 'White must open'),
                                ({'label': 'Second'}, 'opening label')]:
            with self.subTest(change=change):
                edit, timeline = fixture()
                edit['opening'].update(change)
                with self.assertRaisesRegex(ValueError, message):
                    HELPER.plan_edit(edit, timeline, source_meta())

    def test_camps_cannot_be_silently_changed(self):
        edit, timeline = fixture()
        edit['black_label'] = 'Another character'
        with self.assertRaisesRegex(ValueError, 'black_label must match'):
            HELPER.plan_edit(edit, timeline, source_meta())

    def test_wrong_native_dimensions_are_refused(self):
        edit, timeline = fixture()
        with self.assertRaisesRegex(ValueError, 'source_dimensions must match'):
            HELPER.plan_edit(edit, timeline, source_meta(1920, 1080))

    def test_annotations_in_deleted_gaps_are_refused(self):
        edit, timeline = fixture()
        edit['annotations'][1]['original_at'] = 1.5
        with self.assertRaisesRegex(ValueError, 'exactly one retained cut'):
            HELPER.plan_edit(edit, timeline, source_meta())

    def test_retained_cuts_cannot_overlap_or_exceed_source(self):
        for change in ({'in': .9}, {'out': 4.1}):
            with self.subTest(change=change):
                edit, timeline = fixture()
                edit['cuts'][1].update(change)
                with self.assertRaisesRegex(ValueError, 'inside the source'):
                    HELPER.plan_edit(edit, timeline, source_meta())

    def test_death_note_decisions_and_duration_remain_unchanged(self):
        edit = json.loads((HERE / 'episodes/light-vs-l.edit.json').read_text())
        timeline = json.loads((HERE / 'episodes/light-vs-l.json').read_text())
        planned, cuts, frames, _ = HELPER.plan_edit(edit, timeline, source_meta(1920, 1080, 387.4287083333333))
        self.assertEqual(len(cuts), 13)
        self.assertEqual(frames, 3168)
        self.assertEqual([a['source_at'] for a in planned['annotations']],
                         [4.85, 23.05, 27.766666667, 54.733333333, 68.766666667, 82.85, 92.983333333])
        self.assertAlmostEqual(planned['source_out'] + 16 + 12 + sum(a['hold_seconds'] for a in planned['annotations']), 182.6)
        self.assertEqual(planned['opening']['label'], 'L')
        self.assertEqual(planned['opening']['source_at'], 17.7)


class ConversationPlanTests(unittest.TestCase):
    def test_partial_first_opening_uses_edit_evidence_and_later_cut_start_is_remapped(self):
        edit, timeline = conversation_fixture()
        original = copy.deepcopy((edit, timeline))
        planned, _, _, _ = HELPER.plan_edit(edit, timeline, source_meta())
        chapters = planned['conversations']
        self.assertEqual([c['source_at'] for c in chapters], [0, .5])
        self.assertEqual([c['original_source_at'] for c in chapters], [0, 2])
        self.assertEqual([c['opening']['source_at'] for c in chapters], [0, .5])
        self.assertEqual([c['opening']['original_source_at'] for c in chapters], [.5, 2])
        self.assertEqual(chapters[0]['opening']['evidence'], edit['opening']['evidence'])
        self.assertEqual(chapters[1]['opening']['evidence'], timeline['conversations'][1]['opening']['evidence'])
        self.assertEqual(planned['opening'], chapters[0]['opening'])
        self.assertEqual((chapters[1]['white_label'], chapters[1]['black_label']), ('Second', 'First'))
        self.assertEqual([a['source_at'] for a in planned['annotations']], [.25, 1.25])
        self.assertEqual((edit, timeline), original)

    def test_chapter_start_inside_retained_cut_maps_without_changing_its_scope(self):
        edit, timeline = conversation_fixture()
        timeline['conversations'][1]['source_at'] = 2.5
        timeline['conversations'][1]['opening']['source_at'] = 2.5
        planned, _, _, _ = HELPER.plan_edit(edit, timeline, source_meta())
        self.assertEqual([c['source_at'] for c in planned['conversations']], [0, 1])
        self.assertEqual(planned['conversations'][1]['opening']['source_at'], 1)
        self.assertEqual([a['source_at'] for a in planned['annotations']], [.25, 1.25])

    def test_adjacent_cuts_use_half_open_boundary_for_new_chapter(self):
        edit, timeline = conversation_fixture()
        edit['cuts'][0]['out'] = 2
        planned, _, _, _ = HELPER.plan_edit(edit, timeline, source_meta())
        self.assertEqual(planned['conversations'][1]['source_at'], 1.5)
        self.assertEqual(planned['annotations'][1]['source_at'], 2.25)

    def test_later_opening_cannot_be_deleted_even_if_later_dialogue_is_retained(self):
        edit, timeline = conversation_fixture()
        edit['cuts'][1]['in'] = 2.1
        with self.assertRaisesRegex(ValueError, 'opening must remain.*silently omit'):
            HELPER.plan_edit(edit, timeline, source_meta())

    def test_whole_later_chapter_cannot_be_silently_dropped(self):
        edit, timeline = conversation_fixture()
        edit['cuts'] = edit['cuts'][:1]
        edit['annotations'] = edit['annotations'][:1]
        with self.assertRaisesRegex(ValueError, 'opening must remain.*silently omit'):
            HELPER.plan_edit(edit, timeline, source_meta())

    def test_later_chapter_cannot_replace_removed_first_chapter(self):
        edit, timeline = conversation_fixture()
        edit['cuts'] = edit['cuts'][1:]
        edit['opening']['source_at'] = 2
        edit['annotations'] = edit['annotations'][1:]
        with self.assertRaisesRegex(ValueError, 'first retained cut must stay in the first conversation'):
            HELPER.plan_edit(edit, timeline, source_meta())

    def test_annotation_cannot_be_retimed_into_another_chapter(self):
        edit, timeline = conversation_fixture()
        edit['annotations'][0]['original_at'] = 2.5
        with self.assertRaisesRegex(ValueError, 'cannot migrate to another conversation'):
            HELPER.plan_edit(edit, timeline, source_meta())

    def test_annotation_at_chapter_opening_is_ambiguous_on_either_source_clock(self):
        for clock in ('base', 'retained'):
            with self.subTest(clock=clock):
                edit, timeline = conversation_fixture()
                if clock == 'base':
                    timeline['annotations'][1]['source_at'] = 2
                else:
                    edit['annotations'][1]['original_at'] = 2
                with self.assertRaisesRegex(ValueError, 'cannot coincide with a conversation opening'):
                    HELPER.plan_edit(edit, timeline, source_meta())

    def test_first_global_metadata_and_all_chapter_resets_are_required(self):
        changes = [
            ('global_score', 'global camps'), ('global_control', 'global camps'),
            ('first_camp', 'global camps'), ('first_start', 'first conversation must start'),
            ('global_opening_start', 'global opening.source_at'),
            ('chapter_score', 'must restart'), ('chapter_control', 'must restart'),
            ('bool_control', 'must restart')]
        for change, message in changes:
            with self.subTest(change=change):
                edit, timeline = conversation_fixture()
                if change == 'global_score':
                    timeline['initial_score_text'] = '1.0'
                elif change == 'global_control':
                    timeline['initial_control'] = .6
                elif change == 'first_camp':
                    timeline['conversations'][0]['black_label'] = 'Third'
                elif change == 'first_start':
                    timeline['conversations'][0]['source_at'] = .1
                    timeline['conversations'][0]['opening']['source_at'] = .1
                elif change == 'global_opening_start':
                    timeline['opening']['source_at'] = .1
                elif change == 'chapter_score':
                    timeline['conversations'][1]['initial_score_text'] = '0'
                else:
                    timeline['conversations'][1]['initial_control'] = True if change == 'bool_control' else .6
                with self.assertRaisesRegex(ValueError, message):
                    HELPER.plan_edit(edit, timeline, source_meta())

    def test_chapter_openings_require_actual_order_labels_and_review_evidence(self):
        changes = [
            ('empty', 'nonempty ordered list'), ('unordered', 'strictly ordered'),
            ('boolean_start', 'strictly ordered'), ('unreviewed', 'White-first evidence'),
            ('black_opening', 'White-first evidence'), ('missing_evidence', 'White-first evidence'),
            ('wrong_opening_label', 'White-first evidence'), ('wrong_opening_time', 'opening.source_at'),
            ('same_camps', 'camps must differ'), ('empty_camp', 'White and Black labels')]
        for change, message in changes:
            with self.subTest(change=change):
                edit, timeline = conversation_fixture()
                chapter = timeline['conversations'][1]
                if change == 'empty':
                    timeline['conversations'] = []
                elif change == 'unordered':
                    chapter['source_at'] = 0
                elif change == 'boolean_start':
                    chapter['source_at'] = True
                elif change == 'unreviewed':
                    chapter['opening']['reviewed'] = False
                elif change == 'black_opening':
                    chapter['opening']['speaker'] = 'black'
                elif change == 'missing_evidence':
                    del chapter['opening']['evidence']
                elif change == 'wrong_opening_label':
                    chapter['opening']['label'] = 'First'
                elif change == 'wrong_opening_time':
                    chapter['opening']['source_at'] = 2.1
                elif change == 'same_camps':
                    chapter['black_label'] = chapter['white_label']
                else:
                    chapter['black_label'] = ' '
                with self.assertRaisesRegex(ValueError, message):
                    HELPER.plan_edit(edit, timeline, source_meta())

    def test_chapter_cuts_cannot_add_source_outside_the_reviewed_original_interval(self):
        edit, timeline = conversation_fixture()
        timeline['source_out'] = 2.9
        with self.assertRaisesRegex(ValueError, 'cuts must stay inside'):
            HELPER.plan_edit(edit, timeline, source_meta())


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg and FFprobe are required for native-media checks')
class NativeMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='chess source edit test ')
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / 'synthetic source 720.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n',
                        '-f', 'lavfi', '-i', 'color=c=red:s=1280x720:r=30:d=2',
                        '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720:r=30:d=2',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=4',
                        '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]',
                        '-map', '[v]', '-map', '2:a', '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-threads', '2', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-t', '4', str(cls.source)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def invoke(self, name, edit, timeline=None):
        editfile = self.root / (name + '.json')
        output = self.root / (name + ' output')
        edit['source_sha256'] = HELPER.digest(self.source)
        edit['timeline'] = 'base.json'
        editfile.write_text(json.dumps(edit))
        (self.root / 'base.json').write_text(json.dumps(fixture()[1] if timeline is None else timeline))
        result = subprocess.run([sys.executable, str(HERE / 'prepare-source-edit.py'),
                                 '--source', str(self.source), '--edit', str(editfile), '--out', str(output)],
                                capture_output=True, text=True)
        return result, output

    def test_cli_missing_opening_is_rejected_before_writing_media(self):
        edit, _ = fixture()
        del edit['opening']
        result, output = self.invoke('missing opening', edit)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('own explicitly reviewed opening', result.stderr)
        self.assertFalse(output.exists())

    def test_cli_omitted_chapter_is_rejected_before_writing_media(self):
        edit, timeline = conversation_fixture()
        edit['cuts'] = edit['cuts'][:1]
        edit['annotations'] = edit['annotations'][:1]
        result, output = self.invoke('omitted chapter', edit, timeline)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('do not silently omit a chapter', result.stderr)
        self.assertFalse(output.exists())

    def test_cli_false_dimensions_are_rejected_before_writing_media(self):
        edit, _ = fixture()
        edit['source_dimensions'] = {'width': 1920, 'height': 1080}
        result, output = self.invoke('false dimensions', edit)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source_dimensions must match', result.stderr)
        self.assertFalse(output.exists())

    def test_real_720_cut_preserves_picture_audio_geometry_and_remapping(self):
        result, output = self.invoke('native cut', fixture()[0])
        self.assertEqual(result.returncode, 0, result.stderr)
        edited = output / 'scene-edit-1280x720.mkv'
        self.assertTrue(edited.is_file())
        self.assertFalse((output / 'scene-edit-1080.mkv').exists())
        probe = HELPER.media_probe(edited, count_frames=True)
        video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        self.assertEqual((video['width'], video['height'], int(video['nb_read_frames'])), (1280, 720, 45))
        pixels = subprocess.check_output(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(edited),
                                          '-vf', r'select=eq(n\,0)+eq(n\,15),scale=1:1', '-fps_mode', 'vfr',
                                          '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
        self.assertEqual(len(pixels), 6)
        self.assertGreater(pixels[0], 240)
        self.assertLess(pixels[2], 15)
        self.assertGreater(pixels[5], 240)
        self.assertLess(pixels[3], 15)
        pcm = subprocess.check_output(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(edited),
                                       '-map', '0:a:0', '-f', 's16le', '-'])
        self.assertEqual(len(pcm), 45 * 1600 * 2 * 2)
        planned = json.loads((output / 'timeline.json').read_text())
        self.assertEqual([a['source_at'] for a in planned['annotations']], [.25, 1.25])
        self.assertEqual(planned['opening']['evidence'], fixture()[0]['opening']['evidence'])
        self.assertFalse(planned['youtube_clearance_verified'])
        self.assertFalse(planned['source_quality']['accepted_for_final'])
        self.assertEqual(planned['source_edit']['native_dimensions'], {'width': 1280, 'height': 720})


if __name__ == '__main__':
    unittest.main()
