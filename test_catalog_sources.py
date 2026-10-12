import unittest

from app_catalog import load_catalog


class CatalogSourcesTests(unittest.TestCase):
    def test_official_catalog_exposes_downloadable_sources(self):
        entries = {entry['id']: entry for entry in load_catalog([], remote=False)}
        for app_id in ('nebula', 'atlas', 'cosmos', 'stardust', 'ephemeris', 'nova', 'singularity'):
            with self.subTest(app_id=app_id):
                self.assertTrue(entries[app_id]['git_url'].startswith('https://github.com/Sonaed/'))
                self.assertTrue(entries[app_id]['version'])


if __name__ == '__main__':
    unittest.main()
