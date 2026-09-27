"""Qui peut se brancher sur qui — décidé par Existence, lu par tous les hôtes.

Règle, dans l'ordre :
1. le catalogue (apps.json) déclare ``compatible_hosts`` pour un astre → cette liste ;
2. le manifest du module déclare ``hosts`` → cette liste ;
3. sinon ``host_universe`` ;
4. sinon, compatible si l'univers offre toutes les ``host_capabilities`` du module.
Sans aucune information, le module est accepté partout (comportement historique).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

APPS_JSON = Path.home() / ".config" / "existence" / "apps.json"

# Modules applicatifs (processus séparés) : leurs hôtes compatibles.
APP_MODULE_HOSTS = {
    "nova": ("nebula",),
    "singularity": ("nebula", "nova", "atlas"),
}


def load_apps(path: Path = APPS_JSON) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [a for a in data if isinstance(a, dict)]
    except (OSError, ValueError):
        return []


def module_hosts(app: dict) -> list[str]:
    hosts = [h for h in (app.get("orbits") or []) if h]
    if app.get("orbit_of") and app["orbit_of"] not in hosts:
        hosts.insert(0, app["orbit_of"])
    return hosts


def _manifest(module_id: str):
    try:
        from modules.registry import default_registry
        return default_registry().manifest(module_id)
    except Exception:  # noqa: BLE001
        return None


def compatible_hosts(module: dict | str, apps: Iterable[dict] | None = None) -> list[str] | None:
    """Liste des univers acceptés, ou None = aucune restriction connue."""
    module_id = module if isinstance(module, str) else module.get("id", "")
    entry = module if isinstance(module, dict) else {}
    if entry.get("compatible_hosts"):
        return list(entry["compatible_hosts"])
    if module_id in APP_MODULE_HOSTS:
        return list(APP_MODULE_HOSTS[module_id])
    manifest = _manifest(module_id)
    if manifest is None:
        return None
    if getattr(manifest, "hosts", ()):
        return list(manifest.hosts)
    if manifest.host_universe:
        return [manifest.host_universe]
    needs = set(manifest.host_capabilities or ())
    if not needs or apps is None:
        return None
    return [a["id"] for a in apps if a.get("app_kind") == "universe" and needs <= set(a.get("capabilities") or [])]


def is_compatible(module: dict | str, host_id: str, apps: Iterable[dict] | None = None) -> bool:
    allowed = compatible_hosts(module, apps)
    return allowed is None or host_id in allowed


def plugged_modules(host_id: str, apps: Iterable[dict] | None = None) -> list[dict]:
    """Modules branchés sur ``host_id`` ET compatibles avec lui."""
    apps = list(apps if apps is not None else load_apps())
    out = []
    for app in apps:
        if app.get("app_kind") not in {"orbital_module", "universe"} or app.get("id") == host_id:
            continue
        if host_id not in module_hosts(app):
            continue
        if not app.get("installed", True) or app.get("lifecycle_state") == "closed":
            continue
        if is_compatible(app, host_id, apps):
            out.append(app)
    return out


__all__ = ["compatible_hosts", "is_compatible", "plugged_modules", "module_hosts", "load_apps", "APP_MODULE_HOSTS"]
