"""Où vivent les apps de l'écosystème — installées par paquet ou en développement.

Ordre de recherche pour une app :
  1. $EXISTENCE_<ID>_DIR           (ex. EXISTENCE_NEBULA_DIR)
  2. $EXISTENCE_APPS_DIR/<id>
  3. /usr/share/existence/<id>     (paquets .deb / AUR)
  4. ~/Documents/<Dossier>         (copie de développement)
Sans rien d'existant, le chemin de développement est renvoyé.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SYSTEM_ROOT = Path("/usr/share/existence")
APP_FOLDERS = {
    "existence": "Existence", "nebula": "Nebula", "atlas": "Atlas", "cosmos": "Cosmos",
    "stardust": "StarDust", "singularity": "Singularity", "nova": "Nova",
}


def app_dir(app_id: str) -> Path:
    candidates = []
    override = os.environ.get(f"EXISTENCE_{app_id.upper()}_DIR", "").strip()
    if override:
        candidates.append(Path(override))
    apps_dir = os.environ.get("EXISTENCE_APPS_DIR", "").strip()
    if apps_dir:
        candidates.append(Path(apps_dir) / app_id)
    candidates.append(SYSTEM_ROOT / app_id)
    dev = Path.home() / "Documents" / APP_FOLDERS.get(app_id, app_id)
    candidates.append(dev)
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return dev


def is_packaged(app_id: str) -> bool:
    try:
        return app_dir(app_id).resolve().is_relative_to(SYSTEM_ROOT)
    except (OSError, ValueError):
        return False


def launcher(app_id: str) -> str:
    """Commande système installée par le paquet (/usr/bin/existence-<id>), sinon ''."""
    found = shutil.which(f"existence-{app_id}")
    return found if (found and is_packaged(app_id)) else ""


def python() -> str:
    return sys.executable or shutil.which("python3") or "python3"


def native(app_id: str, name: str, dev_build: str) -> str:
    """Binaire compilé : bin/ dans un paquet, dossier de build en développement."""
    root = app_dir(app_id)
    packaged = root / "bin" / name
    return str(packaged if packaged.exists() else root / dev_build / name)


__all__ = ["app_dir", "is_packaged", "launcher", "python", "native", "APP_FOLDERS", "SYSTEM_ROOT"]
