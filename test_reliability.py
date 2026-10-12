import json
import os
import tempfile
import unittest
from pathlib import Path

from reliability import SessionDiagnostics, atomic_json, read_json


class ReliabilityTests(unittest.TestCase):
    def test_atomic_json_keeps_backup_and_recovers_corruption(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            atomic_json(path, {"version": 1, "value": "old"})
            atomic_json(path, {"version": 1, "value": "new"})
            self.assertEqual(json.loads(path.with_suffix(".json.bak").read_text())["value"], "old")
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(read_json(path)["value"], "old")
            self.assertTrue(path.with_suffix(".json.corrupt").exists())

    def test_session_marker_is_removed_on_clean_close(self):
        with tempfile.TemporaryDirectory() as root:
            old = os.environ.get("EXISTENCE_PROFILE")
            os.environ["EXISTENCE_PROFILE"] = root
            try:
                diag = SessionDiagnostics("test-app")
                self.assertTrue(diag.running.exists())
                diag.close()
                self.assertFalse(diag.running.exists())
            finally:
                if old is None:
                    os.environ.pop("EXISTENCE_PROFILE", None)
                else:
                    os.environ["EXISTENCE_PROFILE"] = old


if __name__ == "__main__":
    unittest.main()
