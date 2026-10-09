from pathlib import Path
import tempfile
import unittest

from production.ovni_smoke import digest, selected_shots


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        image = Path(self.directory.name) / 'reviewed.png'
        image.write_bytes(b'reviewed-image-fixture')
        self.plan = {'shots': [{'id': 'one', 'image': str(image), 'sha256': digest(image),
                               'start': 0, 'end': 4},
                              {'id': 'two', 'image': str(image), 'sha256': digest(image),
                               'start': 4, 'end': 8}]}
        self.approval = {s['id']: {'accepted': True, 'sha256': s['sha256']}
                         for s in self.plan['shots']}

    def test_clips_only_the_test_endpoint(self):
        shots = selected_shots(self.plan, self.approval, 6)
        self.assertEqual([s['end'] for s in shots], [4, 6])
        self.assertEqual(self.plan['shots'][1]['end'], 8)

    def test_rejects_changed_bytes(self):
        Path(self.plan['shots'][0]['image']).write_bytes(b'changed')
        with self.assertRaises(AssertionError):
            selected_shots(self.plan, self.approval, 6)

    def test_rejects_unapproved_shot(self):
        self.approval['one']['accepted'] = False
        with self.assertRaises(AssertionError):
            selected_shots(self.plan, self.approval, 6)

    def test_rejects_gap(self):
        self.plan['shots'][1]['start'] = 5
        with self.assertRaises(AssertionError):
            selected_shots(self.plan, self.approval, 6)

    def test_rejects_long_shot(self):
        self.plan['shots'][0]['end'] = 7
        with self.assertRaises(AssertionError):
            selected_shots(self.plan, self.approval, 6)

    def test_rejects_insufficient_footage(self):
        with self.assertRaises(AssertionError):
            selected_shots(self.plan, self.approval, 10)

    def test_rejects_approval_hash_mismatch(self):
        self.approval['one']['sha256'] = 'wrong'
        with self.assertRaises(AssertionError):
            selected_shots(self.plan, self.approval, 6)


if __name__ == '__main__':
    unittest.main()
