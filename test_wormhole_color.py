"""Compatible live revisions can change format without replacing their link."""
import tempfile
import unittest
from pathlib import Path
from modules.wormhole.wormhole import Wormhole


class ColorRevisionTests(unittest.TestCase):
    def test_nova_can_orbit_both_publication_and_raster_apps(self):
        from modules.compat import compatible_hosts, is_compatible
        self.assertIn('ephemeris', compatible_hosts('nova'))
        self.assertTrue(is_compatible('nova', 'nebula'))
        self.assertTrue(is_compatible('nova', 'ephemeris'))

    def test_format_switch_is_atomic_and_keeps_old_reader_content(self):
        with tempfile.TemporaryDirectory() as directory:
            nova = Wormhole('nova', directory)
            eph = Wormhole('ephemeris', directory)
            sent = nova.send('ephemeris', data=b'original-png', name='photo.png', live=True,
                             meta={'color_mode': 'RGB'})
            link_id = sent['link']
            old = Path(sent['path'])
            self.assertEqual(nova.link(link_id)['meta']['color_mode'], 'RGB')
            revision = nova.publish(link_id, data=b'CMYK-TIFF', name='photo.tif',
                                    meta={'color_mode': 'CMYK', 'icc_profile_embedded': True})
            updated = eph.updates({link_id: 1})[0]
            self.assertEqual(revision, 2)
            self.assertEqual(updated['id'], link_id)
            self.assertEqual(updated['apps'], ['nova', 'ephemeris'])
            self.assertEqual(updated['meta']['color_mode'], 'CMYK')
            self.assertEqual(Path(updated['file']).suffix, '.tif')
            self.assertEqual(Path(updated['file']).read_bytes(), b'CMYK-TIFF')
            self.assertEqual(old.read_bytes(), b'original-png')

    def test_existing_publish_clients_remain_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            sender = Wormhole('nova', directory)
            sent = sender.send('nebula', data=b'PNG1', live=True)
            self.assertEqual(sender.publish(sent['link'], data=b'PNG2'), 2)
            self.assertEqual(sender.link(sent['link'])['file'], sent['path'])
            self.assertEqual(Path(sent['path']).read_bytes(), b'PNG2')

    def test_failed_publish_does_not_advance_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            sender = Wormhole('nova', directory)
            sent = sender.send('ephemeris', data=b'first', live=True)
            with self.assertRaises(FileNotFoundError):
                sender.publish(sent['link'], source=Path(directory) / 'missing', name='image.tif')
            self.assertEqual(sender.link(sent['link'])['rev'], 1)
            with self.assertRaises(ValueError):
                sender.publish(sent['link'])
            self.assertEqual(sender.link(sent['link'])['rev'], 1)

    def test_named_revision_cannot_escape_store(self):
        with tempfile.TemporaryDirectory() as directory:
            sender = Wormhole('nova', directory)
            sent = sender.send('ephemeris', data=b'first', live=True)
            sender.publish(sent['link'], data=b'next', name='../../escape.tif')
            self.assertEqual(Path(sender.link(sent['link'])['file']).parent, Path(sent['path']).parent)

    def test_live_link_advertises_schema_colour_and_acknowledgement_state(self):
        with tempfile.TemporaryDirectory() as directory:
            nova = Wormhole('nova', directory)
            eph = Wormhole('ephemeris', directory)
            sent = nova.send('ephemeris', data=b'photo', name='photo.tif', live=True,
                             meta={'color_mode': 'CMYK', 'color_profile': 'FOGRA39',
                                   'icc_profile_sha256': 'abc', 'icc_profile_embedded': True})
            record = nova.link(sent['link'])
            self.assertEqual(record['schema'], 'existence.wormhole-link.v2')
            self.assertEqual(record['meta']['resource']['version'], 1)
            self.assertEqual(record['meta']['colour']['mode'], 'CMYK')
            self.assertEqual(record['meta']['colour']['profile'], 'FOGRA39')
            self.assertEqual(nova.link_status(sent['link'])['state'], 'pending')
            eph.acknowledge(sent['link'], 1)
            self.assertEqual(nova.link_status(sent['link'])['state'], 'synced')
            nova.publish(sent['link'], data=b'new-photo')
            state = nova.link_status(sent['link'])
            self.assertEqual(state['revision'], 2)
            self.assertEqual(state['apps']['nova']['revision'], 2)
            self.assertTrue(state['apps']['ephemeris']['waiting'])

    def test_legacy_link_is_readable_as_the_versioned_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            nova = Wormhole('nova', directory)
            path = Path(directory) / 'asset.png'
            path.write_bytes(b'asset')
            nova.links_path.write_text('{"format":"ExistenceWormholeLinks","links":{"x":{"id":"x","apps":["nova","ephemeris"],"rev":1,"file":"%s","meta":{"color_mode":"RGB"}}}}' % path)
            record = nova.link('x')
            self.assertEqual(record['schema'], 'existence.wormhole-link.v2')
            self.assertEqual(record['meta']['colour']['mode'], 'RGB')


if __name__ == '__main__':
    unittest.main()
