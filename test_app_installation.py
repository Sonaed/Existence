import json
import tempfile
import unittest
from pathlib import Path

from app_installation import (InstallationError, discard_staging, installed_release,
                              managed_target, promote, staging_target,
                              update_available, validate_catalog_entry, version_key)


class InstallationTests(unittest.TestCase):
    def test_target_stays_inside_managed_root(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(managed_target(root, 'nebula'), Path(root).resolve() / 'nebula')
            with self.assertRaises(InstallationError):
                managed_target(root, '../outside')

    def test_staging_is_published_only_after_completion(self):
        with tempfile.TemporaryDirectory() as root:
            staging = staging_target(root, 'nova')
            staging.mkdir(parents=True)
            (staging / 'main.py').write_text('ready')
            target = managed_target(root, 'nova')
            self.assertFalse(target.exists())
            self.assertEqual(promote(staging, target), target)
            self.assertTrue((target / 'main.py').exists())
            with self.assertRaises(InstallationError):
                promote(target, target)

    def test_discard_only_removes_our_staging_directories(self):
        with tempfile.TemporaryDirectory() as root:
            staging = staging_target(root, 'atlas'); staging.mkdir(parents=True)
            discard_staging(staging)
            self.assertFalse(staging.exists())

    def test_manifest_and_version_comparison(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / 'existence-manifest.json').write_text(json.dumps({'version': '26.4.0'}))
            self.assertEqual(installed_release(folder), '26.4.0')
            self.assertTrue(update_available('26.4.0', '26.5.0'))
            self.assertFalse(update_available('26.4.0', '26.4.0'))
            self.assertLess(version_key('26.4.9'), version_key('26.5'))

    def test_rejects_untrusted_source_shape(self):
        validate_catalog_entry({'id': 'nebula', 'git_url': 'https://github.com/Sonaed/Nebula.git'})
        with self.assertRaises(InstallationError):
            validate_catalog_entry({'id': 'Nebula', 'git_url': 'file:///tmp/evil'})


if __name__ == '__main__':
    unittest.main()
