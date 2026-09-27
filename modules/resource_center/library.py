"""Bibliothèque de ressources centrale d'Existence (module Ressources).

UNE seule bibliothèque physique pour tout l'écosystème : Nebula, StarDust,
Atlas, Cosmos… lisent et écrivent au même endroit. Chaque ressource est
étiquetée avec les applications qui peuvent l'utiliser.

    <racine>/<type>/<fichier>          les fichiers (formats inchangés)
    <racine>/library.json              l'index : étiquettes d'apps, auteur, date…

La racine est celle qu'utilisait déjà Nebula
(``~/.local/share/CreativeSystem/resources`` ou ``$CREATIVE_SYSTEM_DATA_HOME``),
donc aucune ressource existante n'est déplacée. Un fichier présent dans un
dossier mais absent de l'index reçoit les étiquettes par défaut de son type.

Aucune dépendance Qt : utilisable par toutes les applications et par Existence.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

INDEX_NAME = "library.json"
INDEX_VERSION = 1

# Applications connues de l'écosystème (ids canoniques Existence).
KNOWN_APPS = ("nebula", "stardust", "atlas", "cosmos", "singularity", "nova")

# Qui peut utiliser quoi par défaut. Modifiable ressource par ressource.
DEFAULT_APPS_BY_KIND: dict[str, tuple[str, ...]] = {
    "brushes": ("nebula",),
    "brush_engines": ("stardust", "nebula"),
    "blends": ("nebula", "stardust"),
    "palettes": ("nebula", "stardust", "atlas", "cosmos"),
    "gradients": ("nebula", "stardust", "atlas", "cosmos"),
    "textures": ("nebula", "stardust", "atlas"),
    "patterns": ("nebula", "atlas"),
    "masks": ("nebula",),
    "images": ("nebula", "atlas", "cosmos", "singularity", "nova"),
    "develop_presets": ("nova",),
    "documents": ("nebula", "atlas", "cosmos"),
    "fonts": ("nebula", "atlas", "cosmos"),
    "styles": ("nebula", "atlas"),
    "filters": ("nebula", "singularity"),
    "effects": ("nebula", "singularity"),
}

APP_LABELS = {"nebula": "Nebula", "stardust": "StarDust", "atlas": "Atlas",
              "cosmos": "Cosmos", "singularity": "Singularity", "nova": "Nova"}


def default_root() -> Path:
    configured = os.environ.get("CREATIVE_SYSTEM_DATA_HOME", "").strip()
    base = Path(configured) if configured else Path.home() / ".local" / "share" / "CreativeSystem"
    return base / "resources"


def slug(value: str) -> str:
    cleaned = re.sub(r"[^\w\- ]+", "", str(value), flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or f"ressource-{uuid.uuid4().hex[:6]}"


class SharedLibrary:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / INDEX_NAME

    # ── index ──
    def _read_index(self) -> dict[str, Any]:
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("entries"), dict):
                return data
        except (OSError, ValueError):
            pass
        return {"format": "ExistenceResourceLibrary", "version": INDEX_VERSION, "entries": {}}

    def _write_index(self, data: dict[str, Any]) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=".library-", suffix=".tmp", dir=self.root)
        os.close(descriptor)
        Path(temporary).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self.index_path)

    def _key(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def _entry_for(self, path: Path, stored: dict | None) -> dict[str, Any]:
        kind = path.parent.name
        entry = dict(stored or {})
        entry.setdefault("apps", list(DEFAULT_APPS_BY_KIND.get(kind, KNOWN_APPS)))
        entry.setdefault("name", path.stem)
        entry.setdefault("owner", "")
        entry.setdefault("tags", [])
        entry["kind"] = kind
        entry["path"] = str(path)
        entry["key"] = self._key(path)
        entry["uri"] = f"resource://existence/resource_center/{kind}/{path.stem}"
        return entry

    # ── lecture ──
    def entries(self, app: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
        stored = self._read_index()["entries"]
        out = []
        kinds = [kind] if kind else sorted(p.name for p in self.root.iterdir() if p.is_dir())
        for k in kinds:
            directory = self.root / k
            if not directory.is_dir():
                continue
            for path in sorted(directory.iterdir()):
                if not path.is_file() or path.name.startswith("."):
                    continue
                entry = self._entry_for(path, stored.get(self._key(path)))
                if app is None or app in entry["apps"]:
                    out.append(entry)
        return out

    def entry(self, path: str | Path) -> dict[str, Any]:
        path = Path(path)
        return self._entry_for(path, self._read_index()["entries"].get(self._key(path)))

    def apps_for(self, path: str | Path) -> list[str]:
        return list(self.entry(path)["apps"])

    # ── écriture ──
    def _register(self, path: Path, apps: Iterable[str] | None, owner: str, name: str | None,
                  extra: dict | None = None) -> dict[str, Any]:
        data = self._read_index()
        key = self._key(path)
        kind = path.parent.name
        record = dict(data["entries"].get(key, {}))
        record.update({
            "apps": sorted(set(apps)) if apps is not None else list(DEFAULT_APPS_BY_KIND.get(kind, KNOWN_APPS)),
            "owner": owner or record.get("owner", ""),
            "name": name or record.get("name") or path.stem,
            "updated_at": time.time(),
        })
        record.setdefault("added_at", time.time())
        if extra:
            record.update(extra)
        data["entries"][key] = record
        self._write_index(data)
        return self._entry_for(path, record)

    def _destination(self, kind: str, filename: str, replace: bool) -> Path:
        directory = self.root / kind
        directory.mkdir(parents=True, exist_ok=True)
        filename = Path(filename).name
        if filename in {"", ".", ".."}:
            raise ValueError("Nom de ressource invalide")
        target = directory / filename
        if target.exists() and not replace:
            target = target.with_name(f"{target.stem}-{uuid.uuid4().hex[:6]}{target.suffix}")
        return target

    def add_file(self, source: str | Path, kind: str, apps: Iterable[str] | None = None, owner: str = "",
                 name: str | None = None, replace: bool = False, extra: dict | None = None) -> dict[str, Any]:
        source = Path(source)
        if not source.is_file():
            raise ValueError(f"Fichier introuvable : {source}")
        target = self._destination(kind, source.name, replace)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return self._register(target, apps, owner, name, extra)

    def add_json(self, kind: str, name: str, payload: dict, apps: Iterable[str] | None = None,
                 owner: str = "", suffix: str = ".json", replace: bool = True,
                 extra: dict | None = None) -> dict[str, Any]:
        """Écrit (ou remplace) une ressource JSON — nouvelle version d'un même nom."""
        target = self._destination(kind, f"{slug(name)}{suffix}", replace)
        descriptor, temporary = tempfile.mkstemp(prefix=".res-", suffix=".tmp", dir=target.parent)
        os.close(descriptor)
        Path(temporary).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, target)
        previous = self._read_index()["entries"].get(self._key(target), {})
        version = int(previous.get("version", 0)) + 1
        merged = {"version": version, **(extra or {})}
        return self._register(target, apps, owner, name, merged)

    def set_apps(self, path: str | Path, apps: Iterable[str]) -> dict[str, Any]:
        path = Path(path)
        entry = self.entry(path)
        return self._register(path, apps, entry.get("owner", ""), entry.get("name"))

    def forget(self, path: str | Path) -> None:
        data = self._read_index()
        data["entries"].pop(self._key(Path(path)), None)
        self._write_index(data)

    def rename_key(self, old: str | Path, new: str | Path) -> None:
        data = self._read_index()
        record = data["entries"].pop(self._key(Path(old)), None)
        if record is not None:
            data["entries"][self._key(Path(new))] = record
            self._write_index(data)


__all__ = ["SharedLibrary", "DEFAULT_APPS_BY_KIND", "KNOWN_APPS", "APP_LABELS", "default_root", "slug"]
