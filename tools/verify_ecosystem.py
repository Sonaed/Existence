#!/usr/bin/env python3
"""Read-only ecosystem health check.

Usage: python tools/verify_ecosystem.py --root /home/deanos/Documents
It never starts a graphical app or modifies a working document.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from modules.contracts import FindingLevel, validate_manifest

APPS = {
    "nebula": ("Nebula", "EXISTENCE/manifest.json", "VERSION", "main.py", "safe recovery in DOCUMENTS/recovery.py"),
    "nova": ("Nova", "existence-manifest.json", None, "main.py", "diagnostic session guard"),
    "stardust": ("StarDust", "existence-manifest.json", None, "main.py", "diagnostic session guard"),
    "ephemeris": ("Ephemeris", "existence-manifest.json", None, "ephemeris.py", "recovery copy + diagnostic session guard"),
    "atlas": ("Atlas", "existence-manifest.json", None, "CMakeLists.txt", "restores last successfully saved Atlas document"),
    "cosmos": ("Cosmos", "existence-manifest.json", "VERSION", "start-desktop.sh", "web workspace autosave"),
    "pulsar": ("Pulsar", "existence-manifest.json", "VERSION", "CMakeLists.txt", "restores last successfully saved Pulsar project"),
    "singularity": ("Singularity", "existence-manifest.json", None, "webready.py", "diagnostic session guard"),
}


def check(root: Path, app_id: str, spec: tuple[str, str | None, str | None, str, str]) -> dict:
    folder, manifest_name, version_name, entry, recovery = spec
    base = root / folder
    result = {"id": app_id, "path": str(base), "checks": [], "status": "pass"}
    def add(name: str, ok: bool, detail: str, *, required: bool = True):
        result["checks"].append({"name": name, "ok": ok, "detail": detail, "required": required})
        if required and not ok:
            result["status"] = "fail"
        elif not ok and result["status"] == "pass":
            result["status"] = "warning"
    add("folder", base.is_dir(), str(base))
    add("entrypoint", (base / entry).exists(), entry)
    if manifest_name:
        manifest_path = base / manifest_name
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            report = validate_manifest(manifest, expected_id=app_id)
            errors = [item.message for item in report.findings if item.level in {FindingLevel.ERROR, FindingLevel.INCOMPATIBLE}]
            add("versioned format", not errors, manifest.get("version", "unknown") if not errors else "; ".join(errors))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            add("versioned format", False, str(exc))
    elif version_name:
        add("versioned format", (base / version_name).is_file(), version_name, required=False)
    else:
        add("versioned format", False, "manifest missing", required=False)
    add("safe session restore", recovery != "not yet declared", recovery, required=False)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=HERE.parent)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = {"format": "existence.ecosystem-health.v1", "root": str(args.root),
              "apps": [check(args.root, key, value) for key, value in APPS.items()]}
    report["ok"] = all(app["status"] != "fail" for app in report["apps"])
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for app in report["apps"]:
            print(f"{app['status'].upper():7} {app['id']}")
            for item in app["checks"]:
                flag = "OK" if item["ok"] else ("WARN" if not item["required"] else "FAIL")
                print(f"  {flag:4} {item['name']}: {item['detail']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
