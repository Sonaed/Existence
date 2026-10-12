import tempfile
import unittest
import os
import subprocess
from pathlib import Path

try:
    from .release import build_manifest, compatible, rollback_file, verify_manifest, verify_signature, write_repository_index, verify_repository_index
except ImportError:
    from release import build_manifest, compatible, rollback_file, verify_manifest, verify_signature, write_repository_index, verify_repository_index


class ReleaseTests(unittest.TestCase):
    def test_manifest_is_sorted_and_hashed(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root); (base / "b").write_text("b"); (base / "a").write_text("a")
            files = build_manifest(base, "26.0")["files"]
            self.assertEqual([item["path"] for item in files], ["a", "b"])
            self.assertEqual(len(files[0]["sha256"]), 64)

    def test_format_policy_rejects_future_versions(self):
        self.assertTrue(compatible("cosmos-workspace", 2))
        self.assertFalse(compatible("cosmos-workspace", 3))

    def test_manifest_verification_and_rollback(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root); target = base / "state"; target.write_text("old"); target.with_suffix(".bak").write_text("backup")
            manifest = base / "manifest.json"; manifest.write_text(__import__("json").dumps(build_manifest(base, "1")))
            self.assertEqual(verify_manifest(base, manifest), [])
            target.write_text("new"); rollback_file(target)
            self.assertEqual(target.read_text(), "backup")

    def test_signature_requires_real_files(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = Path(root) / "manifest.json"
            manifest.write_text("{}")
            self.assertFalse(verify_signature(manifest))

    def test_repository_index_verifies_package_hashes(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root); package = base / "existence-suite.deb"; package.write_bytes(b"package")
            index = write_repository_index(base, base / "repository.json", "26.0")
            self.assertEqual(verify_repository_index(base, index), [])
            package.write_bytes(b"tampered")
            self.assertEqual(verify_repository_index(base, index), ["hash mismatch: existence-suite.deb"])

    def test_real_openpgp_signature_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root); home = base / "gnupg"; home.mkdir(mode=0o700)
            env = dict(os.environ, GNUPGHOME=str(home))
            try:
                subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-gen-key",
                                "Existence Test <test@existence.invalid>", "ed25519", "sign", "0"],
                               env=env, check=True, capture_output=True)
            except subprocess.CalledProcessError as error:
                self.skipTest(f"gpg-agent unavailable: {error.stderr.decode(errors='replace')}")
            manifest = base / "manifest.json"; manifest.write_text("{\"format\":\"test\"}\n")
            signature = manifest.with_suffix(".json.asc")
            subprocess.run(["gpg", "--batch", "--armor", "--detach-sign", "--output", str(signature), str(manifest)],
                           env=env, check=True, capture_output=True)
            self.assertTrue(verify_signature(manifest, signature, home / "pubring.kbx"))
            manifest.write_text("{\"format\":\"tampered\"}\n")
            self.assertFalse(verify_signature(manifest, signature, home / "pubring.kbx"))


if __name__ == "__main__":
    unittest.main()
