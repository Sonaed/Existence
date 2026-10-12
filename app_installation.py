"""Transactional installation primitives used by the Existence catalogue.

The UI owns interaction and process progress.  This module owns the rules that
keep an interrupted download, a malformed catalogue entry or a local edit from
turning into a broken installation.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_VERSION_PART = re.compile(r"\d+")


class InstallationError(ValueError):
    """An installation request cannot safely be applied."""


def validate_catalog_entry(entry: dict[str, Any]) -> None:
    app_id = str(entry.get("id", ""))
    if not _SAFE_ID.fullmatch(app_id):
        raise InstallationError("Identifiant d’application invalide.")
    url = str(entry.get("git_url", "")).strip()
    if url:
        parsed = urlparse(url)
        allowed = parsed.scheme == "https" or url.startswith("git@")
        if not allowed or not parsed.netloc and not url.startswith("git@"):
            raise InstallationError("La source doit être une URL Git HTTPS ou SSH valide.")


def managed_target(root: str | Path, app_id: str) -> Path:
    validate_catalog_entry({"id": app_id})
    base = Path(root).expanduser().resolve()
    target = (base / app_id).resolve()
    if target.parent != base:
        raise InstallationError("Le dossier cible sort du répertoire d’applications.")
    return target


def staging_target(root: str | Path, app_id: str) -> Path:
    target = managed_target(root, app_id)
    return target.with_name(f".{app_id}.installing-{uuid.uuid4().hex[:10]}")


def promote(staging: str | Path, target: str | Path) -> Path:
    """Publie une installation entièrement téléchargée en une opération atomique."""
    staging_path, target_path = Path(staging), Path(target)
    if not staging_path.is_dir():
        raise InstallationError("Le téléchargement n’a pas produit de dossier d’application.")
    if target_path.exists():
        raise InstallationError("Une installation existe déjà à cet emplacement.")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path.replace(target_path)
    return target_path


def discard_staging(path: str | Path) -> None:
    candidate = Path(path)
    if candidate.name.startswith(".") and ".installing-" in candidate.name:
        shutil.rmtree(candidate, ignore_errors=True)


def installed_release(folder: str | Path) -> str:
    """Lit la version déclarée sans importer ni exécuter l’application."""
    base = Path(folder)
    for name in ("existence-manifest.json", "EXISTENCE/manifest.json"):
        manifest = base / name
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
            version = str(value.get("version", "")).strip()
            if version:
                return version
        except (OSError, ValueError, AttributeError):
            continue
    try:
        return (base / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def version_key(value: Any) -> tuple[int, ...]:
    """Natural release ordering for ecosystem versions such as 26.4.0."""
    text = str(value or "")
    pieces = [int(part) for part in _VERSION_PART.findall(text)]
    return tuple((pieces + [0, 0, 0])[:3])


def update_available(installed: Any, available: Any) -> bool:
    return bool(installed and available and version_key(available) > version_key(installed))
