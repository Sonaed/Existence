import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from performance_registry import FORMAT, make_record, save, validate


class PerformanceRegistryTests(unittest.TestCase):
    def test_record_is_versioned_and_replayable(self):
        record = make_record(app="nebula", scenario="8k stroke release",
                             command=["python", "bench.py"], input_file="fixtures/8k.nbl",
                             metrics={"release_ms_median": 65.0}, samples=3,
                             app_root=Path(__file__).parent)
        self.assertEqual(record["format"], FORMAT)
        self.assertIn("source_dirty", record)
        self.assertFalse(validate(record))
        with tempfile.TemporaryDirectory() as directory:
            target = save(Path(directory) / "nebula-stroke.json", record)
            self.assertEqual(json.loads(target.read_text())["scenario"], "8k stroke release")

    def test_incomplete_claim_is_rejected(self):
        self.assertIn("missing scenario", validate({"format": FORMAT, "app": "nebula"}))

    def test_verifier_accepts_a_versioned_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = make_record(app="atlas", scenario="vector open", command=["atlas"], input_file="fixture.atlas",
                                 metrics={"open_ms": 1.0}, samples=1, app_root=Path(__file__).parent)
            save(root / "Atlas/docs/benchmarks/open.json", record)
            result = subprocess.run([sys.executable, "tools/verify_benchmarks.py", "--root", str(root)],
                                    cwd=Path(__file__).parent, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
