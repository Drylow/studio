import errno
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('native_export_storage', Path(__file__).with_name('export-kdenlive.py'))
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class NativeMediaStorageTests(unittest.TestCase):
    def test_default_copy_is_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            source, destination = Path(folder) / 'source', Path(folder) / 'bundle'
            source.write_bytes(b'original-media')
            self.assertEqual(exporter.store_media(source, destination), 'copy')
            self.assertNotEqual(source.stat().st_ino, destination.stat().st_ino)
            source.write_bytes(b'changed-source')
            self.assertEqual(destination.read_bytes(), b'original-media')

    def test_explicit_link_survives_preparation_cache_removal(self):
        with tempfile.TemporaryDirectory() as folder:
            source, destination = Path(folder) / 'source', Path(folder) / 'bundle'
            source.write_bytes(b'immutable-reviewed-media')
            self.assertEqual(exporter.store_media(source, destination, True), 'hardlink')
            self.assertEqual(source.stat().st_ino, destination.stat().st_ino)
            source.unlink()
            self.assertEqual(destination.read_bytes(), b'immutable-reviewed-media')

    def test_cross_filesystem_link_falls_back_to_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            source, destination = Path(folder) / 'source', Path(folder) / 'bundle'
            source.write_bytes(b'reviewed-media')
            with patch.object(exporter.os, 'link', side_effect=OSError(errno.EXDEV, 'cross-device')):
                self.assertEqual(exporter.store_media(source, destination, True), 'copy')
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertNotEqual(source.stat().st_ino, destination.stat().st_ino)

    def test_unexpected_link_failure_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as folder:
            source, destination = Path(folder) / 'source', Path(folder) / 'bundle'
            source.write_bytes(b'reviewed-media')
            with patch.object(exporter.os, 'link', side_effect=OSError(errno.EIO, 'storage failure')):
                with self.assertRaises(OSError):
                    exporter.store_media(source, destination, True)
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
