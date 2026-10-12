"""Conservative plugin loading policy shared by all applications."""
from __future__ import annotations
import json
from pathlib import Path

ALLOWED_PERMISSIONS = {"read_resources", "write_resources", "ipc", "network"}

def validate_plugin(path: str | Path, allowed_root: str | Path) -> tuple[bool, list[str]]:
    p, root = Path(path).resolve(), Path(allowed_root).resolve()
    errors = []
    if root not in p.parents and p != root:
        errors.append("plugin-outside-approved-root")
    manifest = p / ".existence-plugin.json"
    if not manifest.is_file():
        errors.append("manifest-missing")
    else:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if not data.get("id") or not data.get("version"):
                errors.append("identity-incomplete")
            for permission in data.get("permissions", []):
                if permission not in ALLOWED_PERMISSIONS:
                    errors.append(f"permission-not-allowed:{permission}")
        except (OSError, ValueError):
            errors.append("manifest-invalid")
    return not errors, errors
