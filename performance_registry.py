"""Versioned, portable records for performance claims.

The registry intentionally stores measurements rather than promises.  A record
identifies the input, machine, source revision and command so a result can be
repeated or rejected later.
"""
from __future__ import annotations

import json
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FORMAT = "existence.benchmark.v1"


def machine() -> dict[str, str]:
    return {"hostname": socket.gethostname(), "platform": platform.platform(),
            "python": sys.version.split()[0], "machine": platform.machine()}


def git_revision(directory: str | Path) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def git_dirty(directory: str | Path) -> bool | None:
    try:
        return bool(subprocess.check_output(["git", "-C", str(directory), "status", "--porcelain"],
                                            stderr=subprocess.DEVNULL, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def make_record(*, app: str, scenario: str, command: list[str], input_file: str,
                metrics: dict[str, float], samples: int, app_root: str | Path,
                notes: str = "") -> dict[str, Any]:
    if not app or not scenario or not command or not metrics or samples < 1:
        raise ValueError("app, scenario, command, metrics and samples are required")
    return {
        "format": FORMAT, "app": app, "scenario": scenario, "command": list(command),
        "input": input_file, "metrics": {key: float(value) for key, value in metrics.items()},
        "samples": int(samples), "source_revision": git_revision(app_root), "source_dirty": git_dirty(app_root), "machine": machine(),
        "recorded_at": datetime.now(timezone.utc).isoformat(), "notes": notes,
    }


def validate(record: dict[str, Any]) -> list[str]:
    errors = []
    if record.get("format") != FORMAT:
        errors.append("format is not existence.benchmark.v1")
    for field in ("app", "scenario", "command", "input", "metrics", "samples", "source_revision", "machine", "recorded_at"):
        if not record.get(field):
            errors.append(f"missing {field}")
    if not isinstance(record.get("metrics"), dict) or not all(isinstance(v, (int, float)) for v in record.get("metrics", {}).values()):
        errors.append("metrics must be numeric")
    return errors


def save(path: str | Path, record: dict[str, Any]) -> Path:
    errors = validate(record)
    if errors:
        raise ValueError("; ".join(errors))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
