"""Reproducible release manifest, compatibility, and signing helpers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

RELEASE_FORMAT = "existence-release.v1"
FORMAT_POLICY = {"nebula": (1, 1), "nova-sidecar": (1, 1), "cosmos-workspace": (2, 2), "existence-resource": (1, 1)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: str | Path, version: str) -> dict:
    base = Path(root)
    files = [{"path": str(p.relative_to(base)), "size": p.stat().st_size, "sha256": sha256(p)}
             for p in sorted(base.rglob("*")) if p.is_file() and ".git" not in p.parts]
    return {"format": RELEASE_FORMAT, "version": version, "source_date_epoch": int(os.environ.get("SOURCE_DATE_EPOCH", "0")), "files": files}


def write_manifest(root: str | Path, output: str | Path, version: str) -> Path:
    target = Path(output)
    target.write_text(json.dumps(build_manifest(root, version), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def sign(manifest: str | Path, key: str | None = None) -> Path:
    path = Path(manifest)
    signature = path.with_suffix(path.suffix + ".asc")
    command = ["gpg", "--batch", "--yes", "--armor", "--detach-sign", "--output", str(signature)]
    if key:
        command += ["--local-user", key]
    command.append(str(path))
    subprocess.run(command, check=True)
    return signature

def verify_signature(manifest: str | Path, signature: str | Path | None = None,
                     keyring: str | Path | None = None) -> bool:
    """Verify a detached OpenPGP signature; never treats presence as proof."""
    manifest, signature = Path(manifest), Path(signature or (str(manifest) + ".asc"))
    if not manifest.is_file() or not signature.is_file():
        return False
    command = ["gpg", "--batch", "--status-fd", "1"]
    if keyring:
        keyring = Path(keyring)
        command += ["--homedir", str(keyring.parent), "--no-default-keyring", "--keyring", str(keyring)]
    command += ["--verify", str(signature), str(manifest)]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode == 0 and "[GNUPG:] GOODSIG " in result.stdout and "[GNUPG:] VALIDSIG " in result.stdout

def write_repository_index(root: str | Path, output: str | Path, version: str) -> Path:
    """Create deterministic repository metadata for package discovery."""
    base, target = Path(root), Path(output)
    packages = []
    for package in sorted(base.glob("*.deb")) + sorted(base.glob("*.pkg.tar.*")):
        packages.append({"name": package.name, "size": package.stat().st_size,
                         "sha256": sha256(package)})
    target.write_text(json.dumps({"format": "existence-repository.v1", "version": version,
                                  "packages": packages}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target

def verify_repository_index(root: str | Path, index: str | Path) -> list[str]:
    base, data, errors = Path(root), json.loads(Path(index).read_text(encoding="utf-8")), []
    if data.get("format") != "existence-repository.v1":
        errors.append("unsupported repository metadata")
    for item in data.get("packages", []):
        package = base / item["name"]
        if not package.is_file(): errors.append(f"missing: {item['name']}")
        elif sha256(package) != item.get("sha256"): errors.append(f"hash mismatch: {item['name']}")
    return errors


def compatible(format_id: str, version: int) -> bool:
    policy = FORMAT_POLICY.get(format_id)
    return bool(policy and policy[0] <= int(version) <= policy[1])


def verify_manifest(root: str | Path, manifest: str | Path) -> list[str]:
    base = Path(root); data = json.loads(Path(manifest).read_text(encoding="utf-8")); errors = []
    for item in data.get("files", []):
        path = base / item["path"]
        if not path.exists(): errors.append(f"missing: {item['path']}")
        elif sha256(path) != item.get("sha256"): errors.append(f"hash mismatch: {item['path']}")
    return errors


def rollback_file(path: str | Path) -> Path:
    """Recover the last package/config copy from its adjacent .bak."""
    target = Path(path); backup = target.with_suffix(target.suffix + ".bak")
    if not backup.exists(): raise FileNotFoundError(backup)
    target.write_bytes(backup.read_bytes())
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", default="release-manifest.json")
    parser.add_argument("--sign", action="store_true")
    parser.add_argument("--key")
    args = parser.parse_args(argv)
    manifest = write_manifest(args.root, args.output, args.version)
    if args.sign:
        sign(manifest, args.key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
