"""Small, dependency-free reliability primitives shared by ecosystem apps.

All paths are overrideable with ``EXISTENCE_PROFILE`` so tests never touch a
developer's real profile. Writes are durable-before-publish and retain the
last known-good copy when replacing an existing file.
"""
from __future__ import annotations

import faulthandler
import json
import os
import shutil
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def profile_root(app_id: str) -> Path:
    override = os.environ.get("EXISTENCE_PROFILE", "").strip()
    root = Path(override) if override else Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "Existence"
    result = root / app_id.lower()
    try:
        result.mkdir(parents=True, exist_ok=True)
    except OSError:
        result = Path(tempfile.gettempdir()) / "Existence" / app_id.lower()
        result.mkdir(parents=True, exist_ok=True)
    return result


def atomic_bytes(path: str | Path, payload: bytes, *, backup: bool = True) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if backup and target.exists():
            shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def atomic_json(path: str | Path, value: Any, *, backup: bool = True) -> None:
    atomic_bytes(Path(path), json.dumps(value, indent=2, ensure_ascii=False, default=str).encode("utf-8"), backup=backup)


def read_json(path: str | Path, *, app_id: str | None = None, default: Any = None) -> Any:
    target = Path(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
        if value is None:
            raise ValueError("null document")
        return value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        if target.exists():
            corrupt = target.with_suffix(target.suffix + ".corrupt")
            try:
                target.replace(corrupt)
            except OSError:
                pass
        backup = target.with_suffix(target.suffix + ".bak")
        if backup.exists():
            try:
                return json.loads(backup.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass
        return default


class SessionDiagnostics:
    def __init__(self, app_id: str):
        self.root = profile_root(app_id) / "diagnostics"
        self.root.mkdir(parents=True, exist_ok=True)
        self.running = self.root / "running.json"
        self.log_path = self.root / "app.log"
        try:
            self._log = self.log_path.open("a", encoding="utf-8")
        except OSError:
            self.root = Path(tempfile.gettempdir()) / "Existence" / app_id.lower() / "diagnostics"
            self.root.mkdir(parents=True, exist_ok=True)
            self.running = self.root / "running.json"
            self.log_path = self.root / "app.log"
            self._log = self.log_path.open("a", encoding="utf-8")
        self.previous_crash = self.running.exists()
        if self.previous_crash:
            shutil.copy2(self.running, self.root / "previous_session.json")
        atomic_json(self.running, {"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat() }, backup=False)
        faulthandler.enable(self._log, all_threads=True)
        self._old_hook = sys.excepthook
        sys.excepthook = self._hook

    def _hook(self, kind, value, tb):
        self._log.write("".join(traceback.format_exception(kind, value, tb)))
        self._log.flush()
        self._old_hook(kind, value, tb)

    def close(self) -> None:
        try:
            self.running.unlink()
        except OSError:
            pass
        self._log.flush()
        self._log.close()

    def bundle(self, destination: str | Path) -> Path:
        target = Path(destination)
        shutil.make_archive(str(target.with_suffix("")), "zip", self.root)
        return target.with_suffix(".zip")
