"""Run with python -m unittest discover -s experiments/conversation-chess -p test_merge_source_captions.py."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('merge_source_captions', HERE / 'merge-source-captions.py')
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


def cue(start='00:00:00,000', end='00:00:01,000', text='A complete line.', index=1):
    return f'{index}\n{start} --> {end}\n{text}\n'


class MergeSourceCaptionsTests(unittest.TestCase):
    def test_cli_offsets_by_exact_frames_and_preserves_unicode_and_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second, output = root / 'first.srt', root / 'second.srt', root / 'merged.srt'
            first.write_text(cue(text='Échec — LaPadite\nDeuxième ligne.'), encoding='utf-8')
            second.write_text(cue('00:00:00,005', '00:00:00,504', 'Crème et cinéma.'), encoding='utf-8')
            before = [p.read_bytes() for p in (first, second)]
            result = subprocess.run([sys.executable, str(HERE / 'merge-source-captions.py'),
                                     '--first', str(first), '--second', str(second),
                                     '--second-offset-frames', '301', '--fps30', '--out', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            merged = HELPER.parse_srt(output.read_text(encoding='utf-8'))
            self.assertEqual((merged[1].start_ms, merged[1].end_ms), (10038, 10537))
            self.assertEqual(merged[0].text, 'Échec — LaPadite\nDeuxième ligne.')
            self.assertEqual(merged[1].text, 'Crème et cinéma.')
            self.assertEqual([p.read_bytes() for p in (first, second)], before)
            # Two 30-fps frames round up to 67 ms; touching chapters are allowed.
            exact = HELPER.merge_cues([HELPER.Cue(0, 60, 'First')],
                                      [HELPER.Cue(0, 20, 'Second')], 2, 30)
            self.assertEqual((exact[1].start_ms, exact[1].end_ms), (67, 87))
            touching = HELPER.merge_cues([HELPER.Cue(0, 1000, 'First')],
                                         [HELPER.Cue(0, 500, 'Second')], 30, 30)
            self.assertEqual(touching[1].start_ms, touching[0].end_ms)

    def test_rejects_overlap_disorder_and_first_chapter_crossing_exact_offset(self):
        for first, second in [
            ([HELPER.Cue(0, 1000, 'A'), HELPER.Cue(900, 1500, 'B')], [HELPER.Cue(0, 10, 'C')]),
            ([HELPER.Cue(0, 10, 'A')], [HELPER.Cue(100, 200, 'B'), HELPER.Cue(0, 50, 'C')]),
            ([HELPER.Cue(0, 10034, 'A')], [HELPER.Cue(0, 10, 'B')]),
        ]:
            with self.subTest(first=first, second=second), self.assertRaises(ValueError):
                HELPER.merge_cues(first, second, 301, 30)
        with self.assertRaisesRegex(ValueError, 'non-overlapping'):
            HELPER.parse_srt(cue() + '\n' + cue('00:00:00,900', '00:00:01,500', index=2))

    def test_strict_srt_and_invalid_clocks_are_refused_before_output(self):
        malformed = [
            '', cue('00:00:60,000'), cue('00:00:00.000'),
            cue(end='00:00:00,000'), cue(text='  '), cue(index=2),
            cue() + '\n' + cue('00:00:02,000', '00:00:03,000', index=1),
            cue() + 'unexpected\rreturn',
        ]
        for text in malformed:
            with self.subTest(text=text), self.assertRaises(ValueError):
                HELPER.parse_srt(text)
        valid = [HELPER.Cue(0, 10, 'A')]
        for fps in [0, -30, float('nan'), float('inf'), '-inf', True]:
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                HELPER.merge_cues(valid, valid, 30, fps)
        for frames in [-1, 1.5, True]:
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                HELPER.merge_cues(valid, valid, frames, 30)
        with self.assertRaisesRegex(ValueError, 'integer milliseconds'):
            HELPER.merge_cues([HELPER.Cue(float('nan'), 10, 'A')], valid, 30, 30)

    def test_atomic_publication_never_overwrites_even_with_a_concurrent_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'merged.srt'
            output.write_text('Keep the reviewed file.', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                HELPER.atomic_write_new(output, 'Replacement')
            self.assertEqual(output.read_text(), 'Keep the reviewed file.')
            output.unlink()
            real_link = os.link

            def concurrent_writer(source, destination):
                Path(destination).write_text('A concurrent reviewed file.', encoding='utf-8')
                return real_link(source, destination)

            with mock.patch.object(HELPER.os, 'link', side_effect=concurrent_writer):
                with self.assertRaises(FileExistsError):
                    HELPER.atomic_write_new(output, 'Replacement')
            self.assertEqual(output.read_text(), 'A concurrent reviewed file.')
            self.assertEqual(list(root.glob('.merged.srt.*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
