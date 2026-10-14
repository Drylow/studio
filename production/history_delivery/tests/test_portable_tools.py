"""Synthetic/local tests only; these never assert real production or upload success."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalMediaTests(unittest.TestCase):
    def test_normalization_and_video_copy(self):
        normalize = load('normalize_voice')
        identity = load('media_identity')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'synthetic-voice.mp3'
            base = root / 'synthetic-native-base.mp4'
            voice = root / 'normalized.flac'
            proof = root / 'normalization.json'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'sine=frequency=430:sample_rate=44100:duration=8', '-af', 'volume=0.08',
                '-ac', '1', str(source)], check=True)
            measured = normalize.normalize(source, voice, proof)
            self.assertEqual(measured['source_decode'], measured['derived_decode'])
            self.assertEqual(measured['drift_samples'], 0)
            self.assertLess(float(measured['final_levels']['input_tp']), -.3)
            self.assertEqual(normalize.normalize(source, voice, proof), measured)
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'testsrc2=size=320x180:rate=24:duration=8', '-i', str(source),
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(base)], check=True)
            adoption = root / 'vps-adoption'
            adoption.mkdir()
            (adoption / 'voice-adoption.json').write_text(json.dumps({
                'derived_voice_sha256': measured['derived_sha256']}))
            receipt = root / 'synthetic-get-receipt.json'
            receipt.write_text(json.dumps({'project_id': 'synthetic-fixture-project',
                'path': str(base), 'sha256': normalize.digest(base), 'method': 'GET'}))
            final = root / 'synthetic-final.mp4'
            subprocess.run([sys.executable, str(TOOLS / 'master_vps_movie.py'),
                '--episode-dir', str(root), '--project-id', 'synthetic-fixture-project',
                '--output', str(final), '--normalization-proof', str(proof),
                '--base', str(base), '--download-receipt', str(receipt)],
                check=True, capture_output=True)
            self.assertEqual(identity.video_packet_identity(base), identity.video_packet_identity(final))
            master = json.loads((root / 'audio-only-mastering.json').read_text())
            self.assertFalse(master['visual_encoding_performed'])
            self.assertEqual(master['video_codec_mode'], 'copy')

    def test_changed_normalized_input_is_rejected(self):
        normalize = load('normalize_voice')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, target, proof = (root / name for name in ('source', 'target', 'proof.json'))
            source.write_bytes(b'fixture input')
            target.write_bytes(b'changed fixture output')
            proof.write_text(json.dumps({'source_sha256': normalize.digest(source),
                                         'derived_sha256': '0' * 64}))
            with self.assertRaises(ValueError):
                normalize.normalize(source, target, proof)


class PortalClientTests(unittest.TestCase):
    def test_credentials_are_never_sent_to_foreign_or_http_urls(self):
        path = TOOLS.parent / 'tubeforge_support/forge_docs/forge.py'
        spec = importlib.util.spec_from_file_location('canonical_forge', path)
        forge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(forge)
        with patch.object(forge, 'token', side_effect=AssertionError('Token read before host check')):
            for url in ('http://tools.kanye.studio/api', 'https://foreign.example/api',
                        'https://tools.kanye.studio@foreign.example/api'):
                with self.assertRaises(ValueError):
                    forge.request('GET', url)


class AuthoredEvidenceTests(unittest.TestCase):
    def test_captions_require_exact_existing_words(self):
        captions = load('prepare_captions')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script, clock = root / 'script.txt', root / 'clock.json'
            script.write_text('A quiet synthetic test sentence.')
            words = [{'w': word, 's': index * .5, 'e': index * .5 + .4}
                     for index, word in enumerate(script.read_text().split())]
            clock.write_text(json.dumps(words))
            captions.captions(script, clock, root, 4)
            proof = json.loads((root / 'caption-proof.json').read_text())
            self.assertTrue(proof['literal_word_identity'])
            self.assertEqual(proof['canonical_words'], 5)
            words[1]['w'] = 'different'
            clock.write_text(json.dumps(words))
            with self.assertRaises(AssertionError):
                captions.captions(script, clock, root, 4)

    def test_unknown_generation_receipt_remains_unknown(self):
        provenance = load('selected_source_provenance')
        declared = {'prompt': 'Synthetic declared direction', 'referenced_image_paths': []}
        self.assertEqual(provenance.actual_args({'actual_tool_arguments': declared}), declared)
        self.assertIsNone(provenance.actual_args({'actual_tool_arguments': declared,
            'tool_provenance': {'provenance_method': 'orphan source with no associated output receipt'}}))
        self.assertIsNone(provenance.actual_args({'actual_tool_arguments': declared,
            'tool_provenance': {'outputreceipt_available': False}}))


class SiteReaderTests(unittest.TestCase):
    def test_share_code_response_binds_canonical_folder_id(self):
        reader = load('gofile_site_readback')
        from types import SimpleNamespace
        listing = {'type': 'folder', 'id': 'canonical-uuid', 'public': True,
                   'children': {'f': {'id': 'f', 'type': 'file', 'name': 'video.mp4',
                                      'size': 10, 'md5': '0' * 32}}}
        response = SimpleNamespace(url='https://api.gofile.io/contents/PublicShare',
            request=SimpleNamespace(method='GET'), status=200,
            json=lambda: {'status': 'ok', 'data': listing})
        self.assertEqual(reader.observed_listing(response, 'canonical-uuid')['folder_id'],
                         'canonical-uuid')
        self.assertIsNone(reader.observed_listing(response, 'wrong-canonical-uuid'))
        response.url = 'https://foreign.example/contents/PublicShare'
        self.assertIsNone(reader.observed_listing(response, 'canonical-uuid'))

    def test_reader_guard_aborts_mutation_and_foreign_authorization(self):
        reader = load('gofile_site_readback')
        from types import SimpleNamespace
        blocked, unauthorized = [], []
        guard = reader.make_guard(blocked, unauthorized)
        calls = []
        for method, url, headers in [('POST', 'https://api.gofile.io/accounts', {}),
            ('GET', 'https://foreign.example/api', {'Authorization': 'synthetic-fixture'})]:
            route = SimpleNamespace(request=SimpleNamespace(method=method, url=url,
                all_headers=lambda: headers), abort=lambda: calls.append('aborted'),
                continue_=lambda: calls.append('continued'))
            guard(route)
        self.assertEqual(calls, ['aborted', 'aborted'])
        self.assertEqual(len(blocked), 1)
        self.assertEqual(len(unauthorized), 1)


if __name__ == '__main__':
    unittest.main()
