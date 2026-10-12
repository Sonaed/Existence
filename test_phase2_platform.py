import os
import tempfile
import unittest
from pathlib import Path

from modules.contracts import UniverseContract, contract_version_compatible
from modules.plugin_api import PluginContext, PluginRegistry
from modules.resource_center.library import SharedLibrary
from modules.wormhole.wormhole import Wormhole


class Phase2PlatformTests(unittest.TestCase):
    def test_contract_and_plugin_api(self):
        self.assertEqual(UniverseContract("nebula", "1.0").id, "nebula")
        self.assertTrue(contract_version_compatible("1.0", "1.2"))
        self.assertFalse(contract_version_compatible("1.0", "2.0"))
        registry = PluginRegistry(PluginContext("nebula", frozenset({"paint"})))
        registry.command("answer", lambda: 42, capability="paint")
        self.assertEqual(registry.invoke("answer"), 42)

    def test_shared_resource_permissions_dependencies_and_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            library = SharedLibrary(root)
            source = Path(root) / "input.json"
            source.write_text("{}", encoding="utf-8")
            entry = library.add_file(source, "documents", apps=["cosmos"], owner="cosmos")
            library.set_dependencies(entry["path"], ["resource://existence/resource_center/images/base"])
            self.assertTrue(library.can_access(entry["path"], "cosmos"))
            self.assertFalse(library.can_access(entry["path"], "nebula"))
            self.assertEqual(library.export_manifest(entry["path"])["dependencies"],
                             ["resource://existence/resource_center/images/base"])

    def test_wormholes_cover_the_shared_suite_and_are_isolated(self):
        with tempfile.TemporaryDirectory() as root:
            atlas = Wormhole("atlas", root)
            cosmos = Wormhole("cosmos", root)
            self.assertIn("nebula", {x[0] for x in atlas.destinations("image")})
            message = atlas.send("cosmos", data=b"hello", name="x.txt", kind="document")
            received = cosmos.receive()
            self.assertEqual(received[0]["id"], message["id"])


if __name__ == "__main__":
    unittest.main()
