import tempfile
import unittest
from pathlib import Path

from modules.registry import default_registry
from modules.script_creator.runtime import ScriptLifecycle, ScriptPublisher, ScriptSandbox, validate_manifest


MANIFEST = {
    "format": "existence.user-script.v1", "id": "user.batch-export", "name": "Batch Export",
    "version": "1.0.0", "creator": "user", "host_universe": "stardust", "hosts": ["nova"],
    "orbit_of": ["nova"], "entrypoint": "main.py", "permissions": ["catalog.read", "export.write"],
    "capabilities": ["nova.catalog.query", "nova.export.batch"],
    "compatibility": {"existence": "26.1", "nova": "26.1"},
    "commands": [{"id": "batch-export", "label": "Batch Export"}], "parameters": [],
}
SOURCE = "def main(context):\n    print(context['project']['id'])\n    return {'exported': 0}\n"


class ScriptCreatorTests(unittest.TestCase):
    def test_script_creator_is_an_existence_module_hosted_by_stardust(self):
        manifest = default_registry().manifest("script_creator")
        self.assertEqual(manifest.host_universe, "stardust")
        self.assertEqual(manifest.produces, "user_script")
        self.assertIn("nova", MANIFEST["orbit_of"])

    def test_manifest_and_safe_source_validate(self):
        self.assertTrue(validate_manifest(MANIFEST, known_hosts={"nova"}).valid)
        report = ScriptSandbox().run(MANIFEST, SOURCE)
        self.assertTrue(report.valid, report.errors)
        self.assertIn("test-project", report.logs)

    def test_system_access_is_refused_before_execution(self):
        report = ScriptSandbox().run(MANIFEST, "import subprocess\ndef main(context): return {}\n")
        self.assertFalse(report.valid)
        self.assertIn("imports are unavailable in the initial sandbox: subprocess", report.errors)

    def test_publish_authorize_activate_execute_and_version(self):
        with tempfile.TemporaryDirectory() as root:
            publisher = ScriptPublisher(Path(root))
            report = ScriptSandbox().run(MANIFEST, SOURCE)
            first = publisher.publish(MANIFEST, SOURCE, report)
            second = publisher.publish(MANIFEST, SOURCE, report)
            self.assertEqual(first["uri"], "resource://existence/user-scripts/user.batch-export/v1")
            self.assertEqual(second["version"], 2)
            lifecycle = ScriptLifecycle(publisher)
            lifecycle.install("user.batch-export")
            with self.assertRaises(PermissionError):
                lifecycle.activate("user.batch-export")
            lifecycle.authorize("user.batch-export", MANIFEST["permissions"])
            lifecycle.activate("user.batch-export")
            self.assertTrue(lifecycle.execute("user.batch-export").valid)
            lifecycle.deactivate("user.batch-export")
            with self.assertRaises(RuntimeError):
                lifecycle.execute("user.batch-export")
