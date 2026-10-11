"""Regression checks for optional dialogue subtitles and native editable titles."""
import copy
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from dialogue_subtitles import final_srt, map_dialogue_cues, native_title_xml, parse_srt


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('native_export', HERE / 'export-kdenlive.py')
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


def segments():
    return [{'kind': 'intro', 'start_frame': 0, 'end_frame': 480},
            {'kind': 'source', 'source_in': 0, 'source_out': 2, 'start_frame': 480, 'end_frame': 540},
            {'kind': 'analysis', 'start_frame': 540, 'end_frame': 750},
            {'kind': 'source', 'source_in': 2, 'source_out': 4, 'start_frame': 750, 'end_frame': 810},
            {'kind': 'outro', 'start_frame': 810, 'end_frame': 1170}]


class DialogueTimingTests(unittest.TestCase):
    def parse(self, text, duration=4):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'local-English.srt'
            path.write_text(text, encoding='utf-8')
            return parse_srt(path, duration)

    def test_split_across_hold_skips_analysis_and_preserves_later_offset(self):
        cues = self.parse('1\n00:00:01,500 --> 00:00:02,500\nThe decision spans the pause.\n\n'
                          '2\n00:00:03,000 --> 00:00:03,500\nThe reply comes later.\n')
        original = copy.deepcopy(cues)
        mapped = map_dialogue_cues(cues, segments(), 30, 1170)
        self.assertEqual([(c['start_frame'], c['end_frame']) for c in mapped],
                         [(525, 540), (750, 765), (780, 795)])
        self.assertEqual([c['segment_index'] for c in mapped], [1, 3, 3])
        self.assertEqual(cues, original)
        for cue in mapped:
            self.assertTrue(any(s['kind'] == 'source' and s['start_frame'] <= cue['start_frame']
                                < cue['end_frame'] <= s['end_frame'] for s in segments()))
        self.assertIn('00:00:25,000 --> 00:00:25,500', final_srt(mapped, 30))

    def test_overlapping_or_out_of_bounds_source_cues_are_refused(self):
        for text in ['1\n00:00:00,000 --> 00:00:02,000\nFirst.\n\n'
                     '2\n00:00:01,900 --> 00:00:03,000\nSecond.\n',
                     '1\n00:00:03,000 --> 00:00:04,100\nBeyond source.\n',
                     '1\n00:00:02,000 --> 00:00:02,000\nZero length.\n']:
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, 'inside the edited source'):
                    self.parse(text)

    def test_touching_source_cues_remain_nonoverlapping_at_frame_boundary(self):
        cues = self.parse('1\n00:00:00,000 --> 00:00:01,001\nFirst.\n\n'
                          '2\n00:00:01,001 --> 00:00:01,999\nSecond.\n')
        mapped = map_dialogue_cues(cues, segments(), 30, 1170)
        self.assertEqual([(c['start_frame'], c['end_frame']) for c in mapped], [(480, 510), (510, 540)])

    def test_short_cue_and_changed_playback_rate_are_refused(self):
        cues = self.parse('1\n00:00:00,001 --> 00:00:00,004\nToo brief.\n')
        with self.assertRaisesRegex(ValueError, 'shorter than one frame'):
            map_dialogue_cues(cues, segments(), 30, 1170)
        cues = self.parse('1\n00:00:00,500 --> 00:00:01,000\nNormal.\n')
        changed = segments()
        changed[1]['source_out'] = 3
        with self.assertRaisesRegex(ValueError, 'changed scene playback rate'):
            map_dialogue_cues(cues, changed, 30, 1170)

    def test_native_title_has_editable_text_box_and_safe_geometry(self):
        root = ET.fromstring(native_title_xml('A question.\nA quiet reply.', 60))
        self.assertEqual(root.get('out'), '59')
        text = root.find("item[@type='QGraphicsTextItem']/content")
        self.assertEqual(text.text, 'A question.\nA quiet reply.')
        self.assertEqual(text.get('font-pixel-size'), '36')
        box = root.find("item[@type='QGraphicsRectItem']")
        self.assertGreater(int(box.find('position').get('x')), 72)
        self.assertEqual(box.find('content').get('brushcolor'), '0,0,0,136')
        self.assertEqual(root.find('background').get('color'), '0,0,0,0')


def make_native_fixture(root):
    """Small synthetic project: guide, two dialogue shots, hold and outro."""
    from PIL import Image
    source = root / 'source.mp4'
    audio = root / 'dialogue.wav'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'lavfi', '-i',
                    'color=c=0x304858:s=1280x720:r=30:d=2', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=48000:duration=2', '-c:v', 'libx264',
                    '-preset', 'ultrafast', '-threads', '2', '-c:a', 'aac', '-t', '2', str(source)],
                   check=True, capture_output=True)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-i', str(source), '-vn', '-t', '1',
                    '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', str(audio)], check=True, capture_output=True)
    background, overlay = root / 'background.png', root / 'overlay.png'
    Image.new('RGB', (1920, 1080), '#304858').save(background)
    Image.new('RGBA', (1920, 1080), (0, 0, 0, 0)).save(overlay)
    kinds = ['intro', 'source', 'analysis', 'source', 'outro']
    rows = []
    for i, kind in enumerate(kinds):
        row = {'kind': kind, 'start_frame': i * 30, 'end_frame': (i + 1) * 30,
               'duration_frames': 30, 'background_file': str(background), 'graphics_file': str(overlay)}
        if kind == 'source':
            row.update(source_in=0 if i == 1 else 1, source_out=1 if i == 1 else 2,
                       dialogue_audio_file=str(audio))
        rows.append(row)
    manifest = root / 'manifest.json'
    manifest.write_text(json.dumps({'schema': 'conversation-chess-kdenlive-interchange-v1',
        'fps': 30, 'width': 1920, 'height': 1080, 'duration_frames': 150, 'segments': rows,
        'voiceover': False, 'original_source': str(source), 'source_sha256': EXPORT.digest(source),
        'demo': True, 'source_quality': {'minimum_height': 720, 'accepted_for_final': True},
        'title': 'Synthetic dialogue subtitle smoke'}))
    subtitles = root / 'English.srt'
    subtitles.write_text('1\n00:00:00,200 --> 00:00:00,800\nBefore the pause.\n\n'
                         '2\n00:00:01,200 --> 00:00:01,800\nAfter the pause.\n')
    return manifest, subtitles


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg is required for the native project fixture')
class NativeProjectTests(unittest.TestCase):
    def test_optional_config_creates_native_editable_track_and_no_config_does_not(self):
        with tempfile.TemporaryDirectory(prefix='chess caption native ') as temp:
            root = Path(temp)
            manifest, subtitles = make_native_fixture(root)
            plain_project, plain = EXPORT.generate(manifest, root / 'plain')
            self.assertNotIn('subtitles', plain['track_indices'])
            self.assertNotIn('dialogue_subtitles', plain)
            project, report = EXPORT.generate(manifest, root / 'captioned', subtitles)
            self.assertEqual([(c['start_frame'], c['duration_frames']) for c in report['track_clips']['subtitles']],
                             [(36, 18), (96, 18)])
            tree = ET.parse(project)
            title_producers = [p for p in tree.findall('producer')
                               if p.find("property[@name='mlt_service']").text == 'kdenlivetitle']
            self.assertEqual(len(title_producers), 2)
            self.assertEqual(ET.fromstring(title_producers[1].find("property[@name='xmldata']").text)
                             .find("item[@type='QGraphicsTextItem']/content").text, 'After the pause.')
            self.assertTrue((root / 'captioned/subtitles/final-English.srt').is_file())
            self.assertEqual(report['dialogue_subtitles']['source_sha256'], EXPORT.digest(subtitles))


if __name__ == '__main__':
    unittest.main()
