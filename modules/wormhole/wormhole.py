"""Wormholes — transport réel entre les univers d'Existence.

Deux usages :

* **Envoyer** : une app dépose un fichier (calque, image, rendu…) dans la
  boîte d'arrivée d'une autre app. Si la cible n'est pas lancée, Existence la
  démarre et elle ouvre l'envoi au démarrage.
* **Lien en direct** : l'envoi crée un lien partagé. Chaque fois qu'une des
  deux apps publie une nouvelle version, l'autre la reçoit et se met à jour.

Tout passe par des fichiers (aucune dépendance Qt, aucun serveur) ::

    <racine>/alive/<app>.json            battement de cœur (pid, date)
    <racine>/inbox/<app>/<id>.json        envois en attente
    <racine>/store/<id>/<fichier>         contenu transporté
    <racine>/links.json                   liens en direct (révision, auteur…)
    <racine>/log.jsonl                    journal des transferts (pour Existence)

Racine : ``~/.local/share/CreativeSystem/wormholes`` (ou
``$CREATIVE_SYSTEM_DATA_HOME/wormholes``), à côté de la bibliothèque de
ressources.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

# Apps qui savent recevoir par wormhole, et ce qu'elles acceptent.
WORMHOLE_APPS: dict[str, dict[str, Any]] = {
    "nebula": {"name": "Nebula", "accepts": ("image",), "live": True},
    "nova": {"name": "Nova", "accepts": ("image", "raw"), "live": True},
    "singularity": {"name": "Singularity", "accepts": ("image",), "live": False},
}

ALIVE_TIMEOUT = 20.0
APPS_JSON = Path.home() / ".config" / "existence" / "apps.json"


def default_root() -> Path:
    configured = os.environ.get("CREATIVE_SYSTEM_DATA_HOME", "").strip()
    base = Path(configured) if configured else Path.home() / ".local" / "share" / "CreativeSystem"
    return base / "wormholes"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".wh-", suffix=".tmp", dir=path.parent)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
    os.replace(temporary, path)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Wormhole:
    """Point d'accès d'une app aux wormholes."""

    def __init__(self, app_id: str, root: str | Path | None = None) -> None:
        self.app_id = app_id
        self.root = Path(root) if root is not None else default_root()
        for sub in ("alive", "inbox", "store"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        self.inbox = self.root / "inbox" / app_id
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.links_path = self.root / "links.json"
        self.lock_path = self.root / ".lock"

    # ── présence ──
    def heartbeat(self) -> None:
        payload = {"app": self.app_id, "pid": os.getpid(), "time": time.time()}
        _atomic_write(self.root / "alive" / f"{self.app_id}.json", json.dumps(payload).encode())

    def leave(self) -> None:
        with contextlib.suppress(OSError):
            (self.root / "alive" / f"{self.app_id}.json").unlink()

    def is_alive(self, app_id: str) -> bool:
        try:
            data = json.loads((self.root / "alive" / f"{app_id}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return time.time() - float(data.get("time", 0)) < ALIVE_TIMEOUT and _pid_alive(int(data.get("pid", 0)))

    # ── destinations ──
    def destinations(self, kind: str = "image", live: bool = False) -> list[tuple[str, str]]:
        """Apps installées (et branchées si module) capables de recevoir ``kind``."""
        try:
            apps = {a.get("id"): a for a in json.loads(APPS_JSON.read_text(encoding="utf-8")) if isinstance(a, dict)}
        except (OSError, ValueError):
            apps = {}
        result = []
        for app_id, spec in WORMHOLE_APPS.items():
            if app_id == self.app_id or kind not in spec["accepts"] or (live and not spec["live"]):
                continue
            entry = apps.get(app_id)
            if apps and (entry is None or not entry.get("installed", True)):
                continue
            result.append((app_id, (entry or {}).get("name") or spec["name"]))
        return result

    # ── verrou pour links.json ──
    @contextlib.contextmanager
    def _locked(self):
        self.lock_path.touch(exist_ok=True)
        with open(self.lock_path, "r+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _read_links(self) -> dict[str, dict]:
        try:
            data = json.loads(self.links_path.read_text(encoding="utf-8"))
            return data.get("links", {}) if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_links(self, links: dict[str, dict]) -> None:
        _atomic_write(self.links_path, json.dumps({"format": "ExistenceWormholeLinks", "links": links},
                                                  indent=2, ensure_ascii=False).encode())

    def _log(self, event: str, **fields) -> None:
        record = {"time": time.time(), "event": event, "app": self.app_id, **fields}
        with contextlib.suppress(OSError):
            with open(self.root / "log.jsonl", "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ── envoi ──
    def send(self, target: str, source: str | Path | None = None, data: bytes | None = None,
             name: str = "envoi.png", kind: str = "image", live: bool = False,
             meta: dict | None = None) -> dict:
        """Dépose un fichier dans la boîte d'arrivée de ``target``."""
        if target == self.app_id:
            raise ValueError("Une app ne peut pas s'envoyer à elle-même")
        if source is None and data is None:
            raise ValueError("Rien à envoyer")
        message_id = uuid.uuid4().hex[:12]
        filename = Path(name).name or "envoi.png"
        stored = self.root / "store" / message_id / filename
        stored.parent.mkdir(parents=True, exist_ok=True)
        if data is not None:
            _atomic_write(stored, data)
        else:
            shutil.copy2(source, stored)
        message = {
            "id": message_id, "source": self.app_id, "target": target, "kind": kind,
            "name": Path(filename).stem, "path": str(stored), "time": time.time(),
            "meta": dict(meta or {}), "link": "",
        }
        if live:
            link_id = message_id
            with self._locked():
                links = self._read_links()
                links[link_id] = {
                    "id": link_id, "name": message["name"], "kind": kind, "file": str(stored),
                    "apps": [self.app_id, target], "origin": self.app_id, "rev": 1,
                    "writer": self.app_id, "created_at": time.time(), "updated_at": time.time(),
                    "refs": {self.app_id: dict(meta or {})},
                }
                self._write_links(links)
            message["link"] = link_id
        (self.root / "inbox" / target).mkdir(parents=True, exist_ok=True)
        _atomic_write(self.root / "inbox" / target / f"{int(time.time() * 1000)}-{message_id}.json",
                      json.dumps(message, ensure_ascii=False).encode())
        self._log("send", target=target, name=message["name"], live=live, link=message["link"])
        return message

    def control(self, target: str, action: str, **fields) -> dict:
        """Ordre adressé à une app (ex. ``link_active`` : « lie ton calque actif avec X »)."""
        message = {"id": uuid.uuid4().hex[:12], "kind": "control", "action": action,
                   "source": self.app_id, "target": target, "time": time.time(), **fields}
        (self.root / "inbox" / target).mkdir(parents=True, exist_ok=True)
        _atomic_write(self.root / "inbox" / target / f"{int(time.time() * 1000)}-{message['id']}.json",
                      json.dumps(message, ensure_ascii=False).encode())
        self._log("control", target=target, action=action, name=fields.get("to", ""))
        return message

    def pending(self, app_id: str | None = None) -> int:
        folder = self.root / "inbox" / (app_id or self.app_id)
        try:
            return sum(1 for p in folder.iterdir() if p.suffix == ".json")
        except OSError:
            return 0

    def receive(self) -> list[dict]:
        """Retire et retourne les envois en attente (les plus anciens d'abord)."""
        messages = []
        try:
            entries = sorted(p for p in self.inbox.iterdir() if p.suffix == ".json")
        except OSError:
            return messages
        for path in entries:
            taken = path.with_suffix(".taken")
            try:
                os.replace(path, taken)  # un seul lecteur gagne
            except OSError:
                continue
            try:
                message = json.loads(taken.read_text(encoding="utf-8"))
                if isinstance(message, dict) and (message.get("kind") == "control"
                                                  or Path(message.get("path", "")).exists()):
                    messages.append(message)
            except (OSError, ValueError):
                pass
            with contextlib.suppress(OSError):
                taken.unlink()
        if messages:
            self._log("receive", count=len(messages))
        return messages

    # ── liens en direct ──
    def links(self, app_id: str | None = None) -> list[dict]:
        who = app_id or self.app_id
        return [l for l in self._read_links().values() if app_id == "*" or who in l.get("apps", [])]

    def link(self, link_id: str) -> dict | None:
        return self._read_links().get(link_id)

    def attach(self, link_id: str, ref: dict) -> None:
        """Mémorise ce que le lien désigne chez moi (ex. l'id du calque)."""
        with self._locked():
            links = self._read_links()
            if link_id in links:
                links[link_id].setdefault("refs", {})[self.app_id] = dict(ref)
                self._write_links(links)

    def publish(self, link_id: str, source: str | Path | None = None, data: bytes | None = None) -> int:
        """Publie une nouvelle version du lien ; retourne la nouvelle révision."""
        with self._locked():
            links = self._read_links()
            record = links.get(link_id)
            if record is None:
                raise KeyError(link_id)
            target = Path(record["file"])
            if data is not None:
                _atomic_write(target, data)
            elif source is not None:
                _atomic_write(target, Path(source).read_bytes())
            record["rev"] = int(record.get("rev", 1)) + 1
            record["writer"] = self.app_id
            record["updated_at"] = time.time()
            self._write_links(links)
            return record["rev"]

    def updates(self, seen: dict[str, int]) -> list[dict]:
        """Liens modifiés par une AUTRE app depuis la dernière révision vue."""
        changed = []
        for record in self.links():
            rev = int(record.get("rev", 1))
            if rev > int(seen.get(record["id"], 0)) and record.get("writer") != self.app_id:
                changed.append(record)
        return changed

    def unlink(self, link_id: str) -> None:
        with self._locked():
            links = self._read_links()
            record = links.pop(link_id, None)
            self._write_links(links)
        if record:
            self._log("unlink", link=link_id, name=record.get("name", ""))

    def recent(self, limit: int = 40) -> list[dict]:
        try:
            lines = (self.root / "log.jsonl").read_text(encoding="utf-8").splitlines()[-limit:]
        except OSError:
            return []
        out = []
        for line in reversed(lines):
            with contextlib.suppress(ValueError):
                out.append(json.loads(line))
        return out

    def cleanup(self, max_age_days: float = 14) -> None:
        """Supprime les contenus d'envois anciens qui ne portent aucun lien."""
        linked = {Path(l["file"]).parent.name for l in self._read_links().values()}
        limit = time.time() - max_age_days * 86400
        for folder in (self.root / "store").iterdir():
            if folder.name in linked:
                continue
            with contextlib.suppress(OSError):
                if folder.stat().st_mtime < limit:
                    shutil.rmtree(folder, ignore_errors=True)


def load_for(app_id: str) -> Wormhole | None:
    """Aide pour les apps : ``None`` si les wormholes sont inaccessibles."""
    try:
        return Wormhole(app_id)
    except OSError:
        return None


__all__ = ["Wormhole", "WORMHOLE_APPS", "default_root", "load_for"]
