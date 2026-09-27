#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║           EXISTENCE  ·  Creative Universe Hub           ║
║         ArchLinux / Garuda  ·  Space Theme  v2.0        ║
╠══════════════════════════════════════════════════════════╣
║  Nebula · Cosmos · outils en orbite                     ║
╚══════════════════════════════════════════════════════════╝
  Dépendances : python-pyside6  (pacman -S python-pyside6)
  Lancement   : python galaxy_hub.py
"""

import sys
import json
import os
import subprocess
import math
import random
import uuid
import time
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QScrollArea, QFrame,
    QDialog, QFormLayout, QFileDialog, QMessageBox, QInputDialog,
    QComboBox, QTextEdit, QSizePolicy, QGraphicsDropShadowEffect,
    QGridLayout, QSpacerItem, QToolButton, QMenu, QColorDialog,
    QStyleFactory, QStackedWidget, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import (
    Qt, QSize, QTimer, Signal, QRectF, QPointF, QPoint
)
from PySide6.QtGui import (
    QFont, QPixmap, QPainter, QColor, QLinearGradient,
    QPalette, QPen, QRadialGradient, QBrush, QCursor,
    QAction, QFontMetrics, QPainterPath,
    QWindow,
)

from existence_paths import app_dir as _app_dir, launcher as _launcher, native as _native, python as _python
from modules.registry import default_registry
from modules.contracts import apply_manifest_to_catalog, load_manifest_file, load_manifest_command
from existence_ipc import ExistenceIPCRouter, ProcessEndpoint


# ══════════════════════════════════════════════════════════════
#  CONFIG & PALETTE
# ══════════════════════════════════════════════════════════════

APP_VERSION  = "26.0"  # schéma écosystème <année>.<release>
ECOSYSTEM_RELEASE = APP_VERSION
CONFIG_DIR   = Path.home() / ".config" / "existence"
CONFIG_FILE  = CONFIG_DIR / "apps.json"
EVENT_LOG_FILE = CONFIG_DIR / "events.json"
RESOURCE_REGISTRY_FILE = CONFIG_DIR / "resources.json"
WORKSPACE_FILE = CONFIG_DIR / "workspaces.json"
PROJECTS_FILE = CONFIG_DIR / "projects.json"
LEGACY_CONFIG_FILE = Path.home() / ".config" / "galaxy-hub" / "apps.json"

# Galaxy / Space dark palette
C: Dict[str, str] = {
    "bg":        "#080818",
    "bg2":       "#0C0C20",
    "surface":   "#111128",
    "surface_h": "#181838",
    "border":    "#1E1E45",
    "border_h":  "#3A3A80",
    "text":      "#E8E8FF",
    "text2":     "#9090CC",
    "text3":     "#404068",
    "purple":    "#7C3AED",
    "purple_l":  "#A855F7",
    "cyan":      "#06B6D4",
    "pink":      "#D946EF",
    "green":     "#10B981",
    "orange":    "#F97316",
    "red":       "#EF4444",
    "yellow":    "#F59E0B",
    "blue":      "#3B82F6",
}

CATEGORIES = ["Toutes", "Création", "Productivité", "Développement", "Utilitaires", "Autres"]
ECOSYSTEM_ID = "existence"
# Identifiants stables de l'écosystème. Les noms affichés peuvent évoluer,
# mais ces identifiants servent de pont entre catalogue, IPC, sessions et URI.
CANONICAL_IDS = {
    "existence", "nebula", "atlas", "cosmos", "singularity", "stardust",
    "fusion_creator", "resource_center", "palette_creator", "gradient_creator",
    "pixel_art", "nova",
}
IDENTIFIER_ALIASES = {
    "blend_creator": "fusion_creator",
    "blend-creator": "fusion_creator",
    "fusion-creator": "fusion_creator",
    "stellar_dust": "stardust",
    "stellar-dust": "stardust",
    "resource-centre": "resource_center",
    "resource-center": "resource_center",
    "webready": "singularity",
    "palette-creator": "palette_creator",
    "gradient-creator": "gradient_creator",
    "pixel-art": "pixel_art",
}
# Modules Creator branchables sur StarDust : id → types de ressources liés.
# Existence possède le module ET son interface (manifest.interface) ; StarDust
# charge l'interface des modules branchés et s'y adapte.
STARDUST_CREATOR_MODULES = {
    "fusion_creator": ("blend_definition", "blend_result"),
    "palette_creator": ("palette",),
    "gradient_creator": ("gradient",),
}
STRUCTURE_FILTERS = ["Toutes", "Univers", "Modules", "Services", "Infrastructure"]
APP_KIND_LABELS = {
    "environment": "ENVIRONNEMENT",
    "universe": "UNIVERS",
    "orbital_module": "MODULE ORBITAL",
    "service": "SERVICE COMMUN",
    "template": "MODÈLE",
}
ENTITY_TYPES = {"universe", "module", "service", "environment", "template"}
LIFECYCLE_STATES = [
    "not_installed",
    "installed",
    "available",
    "loaded",
    "active",
    "closed",
    "uninstalled",
    "error",
]
RESOURCE_TYPES = ["file", "image", "document", "selection", "project", "event"]
MESSAGE_TYPES = ["export_vector", "open_as_raster", "send_resource", "reference_project", "process_resource"]
ORBIT_RELATION_TYPES = ["visual", "available_from", "depends_on", "uses_capability", "shared_service"]
PERMISSION_TYPES = ["read_resource", "write_resource", "reference_resource", "send_message", "launch_universe", "install_module", "use_service"]
MESSAGE_SEMANTICS = {
    "send_resource": "send",
    "reference_project": "reference",
    "process_resource": "process",
    "export_vector": "send",
    "open_as_raster": "process",
}
MESSAGE_ROUTES = {
    ("atlas", "nebula", "export_vector"): "open_as_raster",
    ("atlas", "cosmos", "send_resource"): "reference_project",
    ("cosmos", "atlas", "reference_project"): "send_resource",
    ("nebula", "atlas", "send_resource"): "send_resource",
    ("nebula", "singularity", "send_resource"): "process_resource",
    ("nebula", "cosmos", "send_resource"): "reference_project",
    ("singularity", "nebula", "send_resource"): "send_resource",
}

UNIVERSE_CONTRACT = {
    "identity": ["id", "name", "version", "app_kind", "ecosystem_id"],
    "lifecycle": ["lifecycle_state", "installed", "exec_path", "working_dir"],
    "resources": ["resource_namespace", "resource_types"],
    "communication": ["capabilities", "accepted_messages", "emitted_messages"],
    "relations": ["orbit_of", "orbit_relation", "map_position"],
    "compatibility": ["existence_min_version", "dependencies", "permissions"],
}
MODULE_CONTRACT = {
    "identity": ["id", "name", "version", "entity_type", "ecosystem_id"],
    "availability": ["availability_state", "installed", "dependencies"],
    "activation": ["activation_state", "orbit_of", "orbit_relation"],
    "capabilities": ["capabilities", "accepted_messages", "emitted_messages"],
    "resources": ["resource_namespace", "resource_types", "resource_bindings"],
    "permissions": ["permissions"],
}

EXISTENCE_MODULES = {
    manifest.id: manifest.to_dict()
    for manifest in default_registry().manifests()
}


TOOLBOX_ID = "__toolbox__"


def module_hosts(app_data: dict) -> List[str]:
    """Univers sur lesquels un module est branché (le premier est l'hôte principal)."""
    hosts = [h for h in (app_data.get("orbits") or []) if h]
    primary = app_data.get("orbit_of") or ""
    if primary and primary not in hosts:
        hosts.insert(0, primary)
    elif primary and hosts and hosts[0] != primary:
        hosts.remove(primary); hosts.insert(0, primary)
    return hosts


def set_module_hosts(app_data: dict, hosts: List[str]) -> None:
    unique: List[str] = []
    for host in hosts:
        if host and host not in unique:
            unique.append(host)
    app_data["orbit_of"] = unique[0] if unique else ""
    app_data["orbits"] = unique


STANDALONE_MODULES = {"nova", "singularity"}


def is_standalone(app_data: dict) -> bool:
    """Module hybride : peut graviter autour d'univers ET exister seul sur la carte."""
    return bool(app_data.get("standalone")) or app_data.get("id") in STANDALONE_MODULES


def on_map_free(app_data: dict) -> bool:
    """Le module hybride a aussi son propre astre libre sur la carte."""
    return is_standalone(app_data) and (bool(app_data.get("map_free")) or not app_data.get("orbit_of")) \
        and app_data.get("orbit_relation") != "toolbox"


def in_toolbox(app_data: dict) -> bool:
    return app_data.get("orbit_relation") == "toolbox" and not app_data.get("orbit_of")


def is_release_version(value: Any) -> bool:
    """Vrai pour le schéma écosystème <année sur 2 chiffres>.<release> (ex. 26.0, 26.3)."""
    import re
    return bool(re.fullmatch(r"\d{2}\.\d+", str(value or "")))


def display_version(app_data: dict) -> str:
    """« Nebula 26.0 » : nom de l'app suivi de sa version."""
    version = str(app_data.get("version") or APP_VERSION)
    return f"{app_data.get('name', app_data.get('id', ''))} {version}".strip()


def canonical_id(value: Any) -> Any:
    """Retourne l'identifiant canonique sans modifier les valeurs libres."""
    if not isinstance(value, str):
        return value
    normalized = value.strip().casefold()
    return IDENTIFIER_ALIASES.get(normalized, normalized)


def canonical_resource_uri(uri: Any) -> Any:
    """Migre les URI Existence dont le propriétaire porte un ancien alias."""
    if not isinstance(uri, str) or not uri.startswith(f"resource://{ECOSYSTEM_ID}/"):
        return uri
    parts = uri.split("/")
    if len(parts) >= 4:
        parts[3] = str(canonical_id(parts[3]))
    return "/".join(parts)


def normalize_app_identity(app_data: dict) -> dict:
    """Normalise les champs qui référencent un univers ou un module."""
    if "id" in app_data:
        app_data["id"] = canonical_id(app_data["id"])
    for field in ("orbit_of",):
        if app_data.get(field):
            app_data[field] = canonical_id(app_data[field])
    for field in ("dependencies", "orbits"):
        if isinstance(app_data.get(field), list):
            app_data[field] = [canonical_id(item) for item in app_data[field]]
    if isinstance(app_data.get("capabilities"), list):
        app_data["capabilities"] = [canonical_id(item) if isinstance(item, str) and item in IDENTIFIER_ALIASES else item
                                     for item in app_data["capabilities"]]
    bindings = app_data.get("resource_bindings")
    if isinstance(bindings, list):
        for binding in bindings:
            if isinstance(binding, dict) and binding.get("consumer"):
                binding["consumer"] = canonical_id(binding["consumer"])
    if app_data.get("resource_namespace"):
        app_data["resource_namespace"] = canonical_resource_uri(app_data["resource_namespace"])
    return app_data


def default_lifecycle_state(app_data: dict) -> str:
    if app_data.get("app_kind") in {"orbital_module", "service"}:
        return "available"
    if app_data.get("system_role"):
        return "active"
    if app_data.get("installed") and app_data.get("exec_path"):
        return "available"
    if app_data.get("install_script") or app_data.get("git_url"):
        return "not_installed"
    return "not_installed"


def normalize_contract(app_data: dict) -> dict:
    """Complète une entrée avec le contrat minimal Existence."""
    normalize_app_identity(app_data)
    app_data.setdefault("ecosystem_id", ECOSYSTEM_ID)
    app_data.setdefault("app_kind", "orbital_module" if app_data.get("orbit_of") else "universe")
    is_module = app_data.get("app_kind") in {"orbital_module", "service"}
    app_data["entity_type"] = "module" if is_module else app_data.get("app_kind", "universe")
    app_data.setdefault("capabilities", [])
    app_data.setdefault("lifecycle_state", default_lifecycle_state(app_data))
    if is_module:
        if app_data.get("lifecycle_state") in {"not_installed", "closed", "uninstalled"}:
            app_data["lifecycle_state"] = "available"
        app_data.setdefault("availability_state", "available")
        app_data.setdefault("activation_state", "inactive")
        if not app_data.get("embedding_mode"):
            app_data["embedding_mode"] = "module"
    else:
        app_data.setdefault("process_state", "stopped")
        app_data.setdefault("session_state", "closed")
        app_data.setdefault("view_state", "external")
    app_data.setdefault("resource_namespace", f"resource://{ECOSYSTEM_ID}/{app_data.get('id', 'unknown')}")
    app_data.setdefault("working_dir", "")
    app_data.setdefault("resource_types", [])
    app_data.setdefault("resource_bindings", [])
    app_data.setdefault("accepted_messages", [])
    app_data.setdefault("emitted_messages", [])
    app_data.setdefault("orbit_relation", "visual" if app_data.get("orbit_of") else "")
    app_data.setdefault("map_position", {})
    app_data.setdefault("dependencies", [])
    app_data.setdefault("permissions", [])
    app_data.setdefault("existence_min_version", APP_VERSION)
    app_data.setdefault("embedding_mode", "external")
    app_data.setdefault("view_protocol", "existence.view.v1")
    return app_data


def is_orbital_module(app_data: dict) -> bool:
    """Retourne la nature effective d'un module, y compris les anciens catalogues."""
    return (
        app_data.get("app_kind") == "orbital_module"
        or app_data.get("id") in {"fusion_creator", "palette_creator", "gradient_creator", "singularity",
                                   "pixel_art", "nova"}
    )


def default_kind(app_id: str) -> str:
    """Nature d'origine d'un astre livré avec Existence (module, service…)."""
    default = next((a for a in DEFAULT_APPS if a.get("id") == app_id), None) if "DEFAULT_APPS" in globals() else None
    return (default or {}).get("app_kind", "")


def can_orbit(app_data: dict) -> bool:
    """Un module ou un service peut être (re)mis en orbite, même après un passage
    par le Void qui l'avait transformé en « univers »."""
    return (is_orbital_module(app_data)
            or app_data.get("app_kind") == "service"
            or default_kind(app_data.get("id", "")) in {"orbital_module", "service"})


def is_module(app_data: dict) -> bool:
    return app_data.get("app_kind") in {"orbital_module", "service"}


def is_universe(app_data: dict) -> bool:
    return app_data.get("app_kind") == "universe"


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


class WorkspaceSessionManager:
    """Session de travail Existence, au-dessus du lifecycle des univers.

    Le catalogue décrit ce qu'est un univers. Cette classe décrit ce que
    l'utilisateur est en train de faire avec ces univers : projet courant,
    ressources ouvertes, workflow et sessions d'univers. Les processus restent
    autonomes ; Existence ne fait que conserver leur contexte et leur identité.
    """

    def __init__(self, apps: Optional[List[Dict]] = None, path: Path = WORKSPACE_FILE):
        self.path = path
        self.apps = apps or []
        self.data = self._load()
        self._ensure_shape()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                value = json.load(f)
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _ensure_shape(self) -> None:
        self.data.setdefault("version", 1)
        self.data.setdefault("current_workspace", "default")
        self.data.setdefault("workspaces", {})
        self.data["workspaces"].setdefault("default", {
            "id": "default",
            "name": "Workspace Existence",
            "current_project": "",
            "active_universes": [],
            "open_resources": [],
            "active_workflow": "",
            "ui": {"windows": {}},
            "updated_at": time.time(),
        })
        if self.data["current_workspace"] not in self.data["workspaces"]:
            self.data["current_workspace"] = "default"
        workspace = self.data["workspaces"][self.data["current_workspace"]]
        workspace.setdefault("current_project", "")
        workspace.setdefault("active_universes", [])
        workspace.setdefault("open_resources", [])
        workspace.setdefault("active_workflow", "")
        workspace.setdefault("restore_on_start", True)
        workspace.setdefault("ui", {"windows": {}})
        workspace["ui"].setdefault("windows", {})
        normalized_sessions = []
        for session in workspace["active_universes"]:
            session["universe_id"] = canonical_id(session.get("universe_id", ""))
            session["resources"] = [canonical_resource_uri(uri) for uri in session.get("resources", [])]
            session.setdefault("resources", [])
            session.setdefault("desired", session.get("state") == "active")
            session.setdefault("window", {"state": "open", "geometry": None})
            normalized_sessions.append(session)
        workspace["active_universes"] = normalized_sessions
        workspace["open_resources"] = [canonical_resource_uri(uri) for uri in workspace.get("open_resources", [])]

    @property
    def current(self) -> Dict[str, Any]:
        self._ensure_shape()
        return self.data["workspaces"][self.data["current_workspace"]]

    def save(self) -> None:
        self.current["updated_at"] = time.time()
        atomic_write_json(self.path, self.data)

    def set_project(self, project: str) -> None:
        self.current["current_project"] = project
        self.save()

    def set_workflow(self, workflow: str) -> None:
        self.current["active_workflow"] = workflow
        self.save()

    def set_restore_on_start(self, enabled: bool) -> None:
        self.current["restore_on_start"] = bool(enabled)
        self.save()

    def add_resource(self, uri: str) -> None:
        uri = canonical_resource_uri(uri)
        if uri and uri not in self.current["open_resources"]:
            self.current["open_resources"].append(uri)
            self.save()

    def remove_resource(self, uri: str) -> None:
        uri = canonical_resource_uri(uri)
        self.current["open_resources"] = [item for item in self.current["open_resources"] if item != uri]
        self.save()

    def session(self, universe_id: str) -> Optional[Dict[str, Any]]:
        universe_id = canonical_id(universe_id)
        return next((item for item in self.current["active_universes"]
                     if item.get("universe_id") == universe_id), None)

    def register_started(self, universe_id: str, pid: int, resources: Optional[List[str]] = None) -> Dict[str, Any]:
        universe_id = canonical_id(universe_id)
        resources = [canonical_resource_uri(uri) for uri in (resources or [])]
        existing = self.session(universe_id)
        if existing:
            existing.update({"pid": pid, "state": "active", "desired": True, "last_opened": time.time()})
            if resources:
                existing["resources"] = list(dict.fromkeys(existing.get("resources", []) + resources))
            session = existing
        else:
            session = {
                "universe_id": universe_id,
                "pid": pid,
                "state": "active",
                "desired": True,
                "resources": resources or [],
                "window": {"state": "open", "geometry": None},
                "last_opened": time.time(),
            }
            self.current["active_universes"].append(session)
        self.current["ui"]["windows"][universe_id] = session["window"]
        self.save()
        return session

    def mark_closed(self, universe_id: str) -> None:
        universe_id = canonical_id(universe_id)
        session = self.session(universe_id)
        if session:
            session["state"] = "closed"
            session["desired"] = False
            session["window"]["state"] = "closed"
            self.save()

    def active_universe_ids(self) -> List[str]:
        return [item["universe_id"] for item in self.current["active_universes"]
                if item.get("state") == "active" and item.get("desired", True)]

    def reconcile_processes(self, apps: List[Dict]) -> List[str]:
        """Réconcilie les sessions externes avec les PID réellement vivants."""
        known = {app.get("id") for app in apps}
        stale = []
        changed = False
        for session in self.current.get("active_universes", []):
            universe_id = canonical_id(session.get("universe_id", ""))
            session["universe_id"] = universe_id
            if universe_id not in known or session.get("state") != "active":
                continue
            # Une vue embarquée sera recréée par Existence ; son ancien PID
            # était celui d'une ancienne instance du hub et n'est pas fiable.
            if session.get("mode") == "embedded_view":
                continue
            pid = int(session.get("pid", 0) or 0)
            alive = False
            if pid > 0:
                try:
                    os.kill(pid, 0)
                    alive = True
                except OSError:
                    alive = False
            if not alive:
                session["state"] = "closed"
                session["desired"] = False
                session.setdefault("window", {})["state"] = "closed"
                stale.append(universe_id)
                changed = True
        if changed:
            self.save()
        return stale

    def required_universe_ids(self, apps: List[Dict], resources: Optional[Dict[str, Dict[str, Any]]] = None) -> List[str]:
        """Universes à restaurer, sans lancer les applications non nécessaires."""
        if not self.current.get("restore_on_start", True):
            return []
        universe_ids = {app.get("id") for app in apps if app.get("app_kind") == "universe"}
        required = [item["universe_id"] for item in self.current["active_universes"]
                    if item.get("universe_id") in universe_ids
                    and item.get("desired", item.get("state") == "active")]
        def owner_from_uri(uri: str) -> str:
            parts = str(uri).split("/")
            return parts[3] if len(parts) >= 4 and parts[0] == "resource:" else ""

        # Une ressource ouverte garde son univers propriétaire dans le workspace.
        for uri in self.current.get("open_resources", []):
            owner = owner_from_uri(uri)
            if owner in universe_ids and owner not in required:
                required.append(owner)
        for session in self.current["active_universes"]:
            if session.get("desired"):
                for uri in session.get("resources", []):
                    owner = owner_from_uri(uri)
                    if owner in universe_ids and owner not in required:
                        required.append(owner)
        return required


class ProjectManager:
    """Contexte de travail persistant, séparé de la Workplace.

    La Workplace décrit les univers vivants et leurs vues. Un Project décrit ce
    sur quoi ils travaillent : ressources, état métier et associations entre
    univers. Les deux peuvent donc changer indépendamment.
    """

    def __init__(self, path: Path = PROJECTS_FILE):
        self.path = path
        self.data = self._load()
        self._ensure_shape()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, encoding="utf-8") as stream:
                value = json.load(stream)
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _ensure_shape(self) -> None:
        self.data.setdefault("version", 1)
        self.data.setdefault("current_project_id", "default")
        self.data.setdefault("mode", "standalone")
        self.data.setdefault("projects", {})
        self.data["projects"].setdefault("default", {
            "id": "default",
            "name": "Projet sans titre",
            "resources": [],
            "universe_resources": {},
            "state": {},
            "created_at": time.time(),
            "updated_at": time.time(),
        })
        if self.data["current_project_id"] not in self.data["projects"]:
            self.data["current_project_id"] = "default"
        for project in self.data["projects"].values():
            project["resources"] = [canonical_resource_uri(uri) for uri in project.get("resources", [])]
            universe_resources = project.get("universe_resources", {})
            project["universe_resources"] = {
                canonical_id(universe_id): [canonical_resource_uri(uri) for uri in resources]
                for universe_id, resources in universe_resources.items()
            }

    @property
    def current(self) -> Dict[str, Any]:
        self._ensure_shape()
        return self.data["projects"][self.data["current_project_id"]]

    def save(self) -> None:
        self.current["updated_at"] = time.time()
        atomic_write_json(self.path, self.data)

    def create(self, name: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        project_id = project_id or str(uuid.uuid4())
        project = {
            "id": project_id,
            "name": name.strip() or "Projet sans titre",
            "resources": [],
            "universe_resources": {},
            "state": {},
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self.data["projects"][project_id] = project
        self.data["current_project_id"] = project_id
        self.data["mode"] = "project"
        self.save()
        return project

    def select(self, project_id: str) -> Dict[str, Any]:
        if project_id not in self.data["projects"]:
            raise KeyError(project_id)
        self.data["current_project_id"] = project_id
        self.data["mode"] = "project"
        self.save()
        return self.current

    def select_or_create(self, name: str) -> Dict[str, Any]:
        normalized = name.strip().casefold()
        for project in self.data["projects"].values():
            if project.get("name", "").strip().casefold() == normalized:
                self.select(project["id"])
                return project
        return self.create(name)

    @property
    def in_project(self) -> bool:
        return self.data.get("mode") == "project"

    def leave_project(self) -> None:
        self.data["mode"] = "standalone"
        self.save()

    def attach_resource(self, universe_id: str, uri: str) -> None:
        universe_id = canonical_id(universe_id)
        uri = canonical_resource_uri(uri)
        if uri not in self.current["resources"]:
            self.current["resources"].append(uri)
        resources = self.current["universe_resources"].setdefault(universe_id, [])
        if uri not in resources:
            resources.append(uri)
        self.save()


def append_event(event_type: str, payload: Dict[str, Any]) -> dict:
    event = {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "time": time.time(),
        **payload,
    }
    try:
        events = []
        if EVENT_LOG_FILE.exists():
            try:
                with open(EVENT_LOG_FILE, encoding="utf-8") as f:
                    events = json.load(f)
            except Exception:
                events = []
        events.append(event)
        atomic_write_json(EVENT_LOG_FILE, events[-200:])
    except OSError as exc:
        event["log_error"] = str(exc)
    return event


class MessageExecutionResult:
    def __init__(self, ok: bool, event: dict, errors: Optional[List[str]] = None):
        self.ok = ok
        self.event = event
        self.errors = errors or []


class ExistingProcessHandle:
    """Handle minimal d'un processus restauré depuis une session persistante."""

    def __init__(self, pid: int):
        self.pid = pid

    def poll(self) -> Optional[int]:
        try:
            os.kill(self.pid, 0)
            return None
        except OSError:
            return 0


class ResourceRegistry:
    """Registre persistant des ressources resource:// partagées par Existence."""

    def __init__(self, apps: Optional[List[Dict]] = None, path: Path = RESOURCE_REGISTRY_FILE):
        self.path = path
        self.resources = self._load()
        if apps:
            self.ensure_app_namespaces(apps)
        self.import_runtime_resources()
        self.sync_shared_library()

    def sync_shared_library(self) -> int:
        """Reflète la bibliothèque centrale (module Ressources) dans le registre.

        Chaque fichier de la bibliothèque devient une ressource
        resource://existence/resource_center/<type>/<nom>, lisible par les
        applications auxquelles elle est étiquetée."""
        try:
            from modules.resource_center.library import SharedLibrary
            library = SharedLibrary()
        except Exception:  # noqa: BLE001 — la bibliothèque est optionnelle
            return 0
        seen = set()
        changed = 0
        for entry in library.entries():
            uri = entry["uri"]
            seen.add(uri)
            item = self.resources.get(uri, {})
            wanted = {
                "uri": uri, "owner": "resource_center", "type": entry["kind"],
                "physical_path": entry["path"], "lifecycle": "active",
                "version": int(entry.get("version", item.get("version", 1)) or 1),
                "access": {"read": list(entry["apps"]) + ["resource_center"], "write": ["resource_center", entry.get("owner") or "resource_center"],
                           "reference": ["*"]},
                "metadata": {"name": entry["name"], "apps": list(entry["apps"]),
                             "producer": entry.get("owner", ""), "library_key": entry["key"]},
            }
            if any(item.get(k) != v for k, v in wanted.items()):
                item.update(wanted)
                item.setdefault("created_at", time.time())
                item["updated_at"] = time.time()
                self.resources[uri] = item
                changed += 1
        for uri, item in list(self.resources.items()):
            if (uri.startswith(f"resource://{ECOSYSTEM_ID}/resource_center/") and uri not in seen
                    and item.get("lifecycle") != "deleted" and item.get("metadata", {}).get("library_key")):
                item["lifecycle"] = "deleted"
                changed += 1
        if changed:
            self._try_save()
            append_event("resource.library_synced", {"count": changed})
        return changed

    def for_app(self, app_id: str) -> list:
        """Ressources utilisables par une application (lecture autorisée)."""
        app_id = canonical_id(app_id)
        self.sync_shared_library()
        return [r for uri, r in self.resources.items()
                if r.get("lifecycle") != "deleted" and self.can_access(app_id, uri, "read")
                and not r.get("metadata", {}).get("namespace")]

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                normalized = {}
                changed = False
                for old_uri, resource in data.items():
                    if not isinstance(resource, dict):
                        continue
                    uri = canonical_resource_uri(resource.get("uri", old_uri))
                    # Copie profonde : les métadonnées peuvent contenir des
                    # identifiants legacy à plusieurs niveaux.
                    item = json.loads(json.dumps(resource))
                    item["uri"] = uri
                    if item.get("owner"):
                        item["owner"] = canonical_id(item["owner"])
                    metadata = item.get("metadata")
                    if isinstance(metadata, dict):
                        for field in ("creator", "producer", "source_app", "owner", "consumer"):
                            if metadata.get(field):
                                metadata[field] = canonical_id(metadata[field])
                    access = item.get("access")
                    if isinstance(access, dict):
                        item["access"] = {
                            mode: [canonical_id(actor) for actor in actors]
                            if isinstance(actors, list) else actors
                            for mode, actors in access.items()
                        }
                    normalized[uri] = item
                    changed = changed or uri != old_uri or item != resource
                if changed:
                    try:
                        atomic_write_json(self.path, normalized)
                    except OSError:
                        pass
                return normalized
        except Exception:
            return {}
        return {}

    def save(self) -> None:
        atomic_write_json(self.path, self.resources)

    def import_runtime_resources(self) -> int:
        """Récupère les descripteurs publiés par les bridges d'univers."""
        runtime_root = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "existence" / "resources"
        if not runtime_root.exists():
            return 0
        imported = 0
        for descriptor_path in runtime_root.rglob("*.json"):
            try:
                descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(descriptor, dict) or not descriptor.get("uri"):
                continue
            uri = canonical_resource_uri(descriptor["uri"])
            if not uri.startswith(f"resource://{ECOSYSTEM_ID}/"):
                continue
            item = dict(descriptor)
            item["uri"] = uri
            item.setdefault("physical_path", "")
            item.setdefault("lifecycle", "active")
            item.setdefault("version", 1)
            item.setdefault("imported_from", str(descriptor_path))
            previous = self.resources.get(uri)
            if previous != item:
                self.resources[uri] = item
                imported += 1
        if imported:
            self._try_save()
            append_event("resource.runtime_imported", {"count": imported, "root": str(runtime_root)})
        return imported

    def ensure_app_namespaces(self, apps: List[Dict]) -> None:
        changed = False
        for app in apps:
            normalize_contract(app)
            uri = app.get("resource_namespace")
            if not uri or uri in self.resources:
                continue
            self.resources[uri] = {
                "uri": uri,
                "owner": app["id"],
                "type": "project",
                "version": 1,
                "physical_path": "",
                "created_at": time.time(),
                "updated_at": time.time(),
                "lifecycle": "active",
                "access": {
                    "read": ["*"],
                    "write": [app["id"]],
                    "reference": ["*"],
                },
                "metadata": {"name": app.get("name", app["id"]), "namespace": True},
            }
            changed = True
        if changed:
            self._try_save()

    def create(
        self,
        owner: str,
        resource_type: str,
        name: str,
        physical_path: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        access: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        owner = canonical_id(owner)
        slug = self._slug(name)
        uri = f"resource://{ECOSYSTEM_ID}/{owner}/{resource_type}/{slug}"
        if uri in self.resources:
            base = uri
            uri = f"{base}-{str(uuid.uuid4())[:8]}"
        resource = {
            "uri": uri,
            "owner": owner,
            "type": resource_type,
            "version": 1,
            "physical_path": physical_path,
            "created_at": time.time(),
            "updated_at": time.time(),
            "lifecycle": "active",
            "access": access or {"read": [owner], "write": [owner], "reference": ["*"]},
            "metadata": metadata or {"name": name},
        }
        self.resources[uri] = resource
        self._try_save()
        append_event("resource.created", {"resource": uri, "owner": owner, "type": resource_type})
        return resource

    def resolve(self, uri: str) -> Optional[Dict[str, Any]]:
        return self.resources.get(canonical_resource_uri(uri))

    def can_access(self, actor: str, uri: str, mode: str = "read") -> bool:
        actor = canonical_id(actor)
        uri = canonical_resource_uri(uri)
        resource = self.resolve(uri)
        if not resource or resource.get("lifecycle") == "deleted":
            return False
        allowed = resource.get("access", {}).get(mode, [])
        return "*" in allowed or actor in allowed or actor == resource.get("owner")

    def delete(self, uri: str, actor: str) -> bool:
        uri = canonical_resource_uri(uri)
        actor = canonical_id(actor)
        if not self.can_access(actor, uri, "write"):
            return False
        resource = self.resources.get(uri)
        if not resource:
            return False
        resource["lifecycle"] = "deleted"
        resource["updated_at"] = time.time()
        resource["version"] = int(resource.get("version", 1)) + 1
        self._try_save()
        append_event("resource.deleted", {"resource": uri, "actor": actor})
        return True

    def update(
        self,
        uri: str,
        actor: str,
        physical_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        versioned: bool = True,
    ) -> Optional[Dict[str, Any]]:
        uri = canonical_resource_uri(uri)
        actor = canonical_id(actor)
        if not self.can_access(actor, uri, "write"):
            return None
        resource = self.resources.get(uri)
        if not resource or resource.get("lifecycle") == "deleted":
            return None
        if physical_path is not None:
            resource["physical_path"] = physical_path
        if metadata:
            resource.setdefault("metadata", {}).update(metadata)
        if versioned:
            resource["version"] = int(resource.get("version", 1)) + 1
            append_event("resource.versioned", {"resource": uri, "actor": actor, "version": resource["version"]})
        resource["lifecycle"] = "modified"
        resource["updated_at"] = time.time()
        self._try_save()
        append_event("resource.updated", {"resource": uri, "actor": actor})
        return resource

    def _try_save(self) -> None:
        try:
            self.save()
        except OSError:
            pass

    @staticmethod
    def _slug(value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
        cleaned = "-".join(part for part in cleaned.split("-") if part)
        return cleaned or str(uuid.uuid4())[:8]


class MessageExecutor:
    """Prototype minimal du transport inter-univers d'Existence."""

    def __init__(self, apps: List[Dict], resources: Optional[ResourceRegistry] = None):
        self.apps = {normalize_app_identity(app)["id"]: normalize_contract(app) for app in apps}
        self.resources = resources or ResourceRegistry(list(self.apps.values()))

    def send_message(
        self,
        source: str,
        target: str,
        message: str,
        resource: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> MessageExecutionResult:
        payload = payload or {}
        source = canonical_id(source)
        target = canonical_id(target)
        resource = canonical_resource_uri(resource)
        event = {
            "id": str(uuid.uuid4()),
            "source": source,
            "target": target,
            "message": message,
            "target_message": MESSAGE_ROUTES.get((source, target, message), message),
            "resource": resource,
            "payload": payload,
            "status": "pending",
        }
        errors = self._validate(event)
        if errors:
            event["status"] = "error"
            event["errors"] = errors
            append_event("message.failed", event)
            return MessageExecutionResult(False, event, errors)

        event["status"] = "executed"
        event["result"] = {
            "kind": "event",
            "message": f"{source}.{message} -> {target}.{event['target_message']}",
            "resource": resource,
        }
        append_event("message.executed", event)
        return MessageExecutionResult(True, event)

    def _validate(self, event: dict) -> List[str]:
        errors = []
        source = self.apps.get(event["source"])
        target = self.apps.get(event["target"])
        if not source:
            errors.append(f"Source inconnue : {event['source']}")
            return errors
        if not target:
            errors.append(f"Cible inconnue : {event['target']}")
            return errors

        blocked_states = {"closed", "uninstalled", "error"}
        if source.get("lifecycle_state") in blocked_states:
            errors.append(f"{source['name']} n'est pas disponible ({source.get('lifecycle_state')}).")
        if target.get("lifecycle_state") in blocked_states:
            errors.append(f"{target['name']} n'est pas disponible ({target.get('lifecycle_state')}).")

        source_permissions = source.get("permissions", [])
        if source_permissions and "send_message" not in source_permissions:
            errors.append(f"{source['name']} n'a pas la permission send_message.")

        if event["message"] not in source.get("emitted_messages", []):
            errors.append(f"{source['name']} n'émet pas le message {event['message']}.")
        if event["target_message"] not in target.get("accepted_messages", []):
            errors.append(f"{target['name']} n'accepte pas le message {event['target_message']}.")

        required_access = self._required_resource_access(event["target_message"])
        required_permission = {
            "read": "read_resource",
            "reference": "reference_resource",
            "write": "write_resource",
        }.get(required_access, "read_resource")

        if not self.resources.resolve(event["resource"]):
            errors.append(f"Ressource introuvable : {event['resource']}")
        elif not self.resources.can_access(event["target"], event["resource"], required_access):
            errors.append(f"{target['name']} ne peut pas accéder à {event['resource']} en mode {required_access}.")

        permissions = target.get("permissions", [])
        if permissions and required_permission not in permissions:
            errors.append(f"{target['name']} n'a pas la permission {required_permission}.")
        return errors

    @staticmethod
    def _required_resource_access(message: str) -> str:
        semantic = MESSAGE_SEMANTICS.get(message, "send")
        if semantic == "reference":
            return "reference"
        if semantic == "process":
            return "read"
        return "read"

DEFAULT_APPS: List[Dict] = [
    {
        "id":           "existence",
        "name":         "Existence",
        "description":  "Terrain commun des univers : ressources, liaisons, gravité et services partagés sans monolithe.",
        "category":     "Développement",
        "icon_emoji":   "✦",
        "icon_path":    "",
        "accent_color": "#A5B4FC",
        "version":      APP_VERSION,
        "installed":    True,
        "exec_path":    str(Path(__file__).resolve()),
        "exec_args":    [],
        "working_dir":  "",
        "install_type": "system",
        "install_script": "",
        "git_url":      "",
        "tags":         ["existence", "terrain", "services", "univers"],
        "orbit_of":     "",
        "system_role":  "core",
        "app_kind":     "environment",
        "capabilities": ["workspace", "context", "resources", "module_graph", "inter_app_communication"],
        "resource_types": ["project", "event"],
        "accepted_messages": ["send_resource", "reference_project", "process_resource"],
        "emitted_messages": ["send_resource", "reference_project"],
    },
    {
        "id":           "common_services",
        "name":         "Services Communs",
        "description":  "Couche partagée pour fichiers, paramètres, ressources, mises à jour et communication entre modules.",
        "category":     "Développement",
        "icon_emoji":   "≡",
        "icon_path":    "",
        "accent_color": "#38BDF8",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "system",
        "install_script": "",
        "git_url":      "",
        "tags":         ["services", "fichiers", "ressources", "paramètres", "communication"],
        "orbit_of":     "existence",
        "system_role":  "common_services",
        "app_kind":     "service",
        "capabilities": ["files", "settings", "updates", "resources", "messages"],
    },
    {
        "id":           "wormhole_access",
        "name":         "Wormhole Access",
        "description":  "Passages entre univers : prépare les liaisons Nebula, Atlas, Cosmos, Singularity et leurs outils.",
        "category":     "Développement",
        "icon_emoji":   "↔",
        "icon_path":    "",
        "accent_color": "#C4B5FD",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "system",
        "install_script": "",
        "git_url":      "",
        "tags":         ["wormhole", "liaison", "passage", "univers", "communication"],
        "orbit_of":     "existence",
        "system_role":  "wormholes",
        "app_kind":     "service",
        "capabilities": ["send_to_universe", "receive_from_universe", "inter_app_bridge"],
        "accepted_messages": MESSAGE_TYPES,
        "emitted_messages": MESSAGE_TYPES,
    },
    {
        "id":           "gravity_layer",
        "name":         "Gravité",
        "description":  "Relations entre modules : dépendances, proximité, appartenance et services partagés.",
        "category":     "Développement",
        "icon_emoji":   "⌁",
        "icon_path":    "",
        "accent_color": "#FBBF24",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "system",
        "install_script": "",
        "git_url":      "",
        "tags":         ["gravité", "dépendances", "relations", "orbite", "modules"],
        "orbit_of":     "existence",
        "system_role":  "gravity",
        "app_kind":     "service",
        "capabilities": ["dependencies", "proximity", "ownership", "active_modules", "workspace_position"],
    },
    {
        "id":           "shared_data_index",
        "name":         "Centralisation Ressources",
        "description":  "Index des ressources communes : Existence les connaît sans forcément les posséder.",
        "category":     "Développement",
        "icon_emoji":   "◆",
        "icon_path":    "",
        "accent_color": "#93C5FD",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "system",
        "install_script": "",
        "git_url":      "",
        "tags":         ["centralisation", "ressources", "données", "index", "atlas", "nebula"],
        "orbit_of":     "common_services",
        "system_role":  "resource_index",
        "app_kind":     "service",
        "capabilities": ["resource_index", "shared_context", "project_references"],
    },
    {
        "id":           "app_installer",
        "name":         "Installateur D'app",
        "description":  "Installe les apps de ton écosystème et demande au vérificateur si elles sont déjà présentes.",
        "category":     "Utilitaires",
        "icon_emoji":   "↓",
        "icon_path":    "",
        "accent_color": "#22D3EE",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "system",
        "install_script": "",
        "git_url":      "",
        "tags":         ["installateur", "app", "univers", "existence"],
        "orbit_of":     "common_services",
        "system_role":  "installer",
        "app_kind":     "service",
        "capabilities": ["install_universe", "install_module", "verify_installation"],
    },
    {
        "id":           "app_install_verifier",
        "name":         "Vérificateur d'app",
        "description":  "Sous-couche de l'installateur : répond simplement si une app Existence est installée ou non.",
        "category":     "Utilitaires",
        "icon_emoji":   "✓",
        "icon_path":    "",
        "accent_color": "#34D399",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "system",
        "install_script": "",
        "git_url":      "",
        "tags":         ["vérificateur", "installation", "installateur", "app", "existence"],
        "orbit_of":     "app_installer",
        "system_role":  "install_verifier",
        "app_kind":     "service",
        "capabilities": ["installed_state"],
    },
    {
        "id":           "app_launcher",
        "name":         "Launcher D'app",
        "description":  "Point de départ : lance un univers ou un outil sans absorber son autonomie.",
        "category":     "Utilitaires",
        "icon_emoji":   "▶",
        "icon_path":    "",
        "accent_color": "#60A5FA",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "system",
        "install_script": "",
        "git_url":      "",
        "tags":         ["launcher", "lancement", "app", "existence"],
        "orbit_of":     "common_services",
        "system_role":  "launcher",
        "app_kind":     "service",
        "capabilities": ["launch_universe", "launch_tool"],
    },
    {
        "id":           "module_orbit_verifier",
        "name":         "Vérificateur des Modules à Lancer/orbite",
        "description":  "Prépare le futur contrôle des modules gravitationnels branchés autour d'un univers.",
        "category":     "Utilitaires",
        "icon_emoji":   "◌",
        "icon_path":    "",
        "accent_color": "#FBBF24",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "system",
        "install_script": "",
        "git_url":      "",
        "tags":         ["module", "orbite", "gravitation", "existence"],
        "orbit_of":     "gravity_layer",
        "system_role":  "module_verifier",
        "app_kind":     "service",
        "capabilities": ["module_state", "orbit_state", "dependencies"],
    },
    {
        "id":           "app_manifest",
        "name":         "App",
        "description":  "Modèle d'application à transformer en univers ou en outil orbital.",
        "category":     "Autres",
        "icon_emoji":   "□",
        "icon_path":    "",
        "accent_color": "#818CF8",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    "python",
        "exec_args":    ["main.py"],
        "working_dir":  str(_app_dir("nebula")),
        "install_type": "manual",
        "install_script": "",
        "git_url":      "",
        "tags":         ["template", "app", "prototype"],
        "orbit_of":     "existence",
        "app_kind":     "template",
        "capabilities": [],
    },
    {
        "id":           "nebula",
        "manifest_path": str(_app_dir("nebula") / "EXISTENCE" / "manifest.json"),
        "name":         "Nebula",
        "description":  "Un univers de création visuelle — là où la matière devient image.",
        "category":     "Création",
        "icon_emoji":   "✦",
        "icon_path":    "",
        "accent_color": "#F062D5",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    _launcher("nebula") or _python(),
        "exec_args":    [] if _launcher("nebula") else ["main.py"],
        "working_dir":  str(_app_dir("nebula")),
        "install_type": "manual",
        "install_script": "",
        "git_url":      "",
        "tags":         ["dessin", "art", "création", "univers"],
        "app_kind":     "universe",
        "embedding_mode": "embeddable_view",
        "view_protocol": "existence.view.v1",
        "capabilities": ["raster_painting", "receive_vector", "send_resource", "fusion", "blend_result", "blend_definition"],
        "resource_types": ["image", "file", "selection", "project"],
        "accepted_messages": ["open_as_raster", "send_resource", "process_resource", "fusion", "blend_result", "blend_definition"],
        "emitted_messages": ["send_resource"],
        "permissions": ["read_resource", "write_resource", "reference_resource", "send_message", "launch_universe"],
    },
    {
        "id":           "cosmos",
        "manifest_path": str(_app_dir("cosmos") / "existence-manifest.json"),
        "name":         "Cosmos",
        "description":  "L'univers où les idées, les notes et les constellations se rencontrent.",
        "category":     "Productivité",
        "icon_emoji":   "🌌",
        "icon_path":    "",
        "accent_color": "#8B5CF6",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    _launcher("cosmos") or str(_app_dir("cosmos") / "start-desktop.sh"),
        "exec_args":    [],
        "working_dir":  str(_app_dir("cosmos")),
        "install_type": "manual",
        "install_script": "",
        "git_url":      "",
        "tags":         ["notes", "knowledge", "productivité", "univers"],
        "app_kind":     "universe",
        "embedding_mode": "embeddable_view",
        "view_protocol": "existence.view.v1",
        "capabilities": ["project_organization", "references", "shared_context"],
        "resource_types": ["document", "project", "file"],
        "accepted_messages": ["reference_project", "send_resource"],
        "emitted_messages": ["reference_project", "send_resource"],
        "permissions": ["read_resource", "write_resource", "reference_resource", "send_message", "launch_universe"],
    },
    {
        "id":           "atlas",
        "manifest_command": [_native("atlas", "AtlasExistenceAdapter", "build_atlas"), "--manifest"],
        "name":         "Atlas",
        "description":  "Univers vectoriel : formes, tracés, composition et échanges vers Nebula.",
        "category":     "Création",
        "icon_emoji":   "△",
        "icon_path":    "",
        "accent_color": "#F472B6",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    _launcher("atlas") or _native("atlas", "CreativeSystemAtlasGtk", "build_atlas"),
        "exec_args":    [],
        "working_dir":  "",
        "install_type": "manual",
        "install_script": "",
        "git_url":      "",
        "tags":         ["vectoriel", "atlas", "illustration", "univers"],
        "app_kind":     "universe",
        "embedding_mode": "embeddable_view",
        "view_protocol": "existence.view.v1",
        "capabilities": ["vector_editing", "send_to_nebula", "receive_resource"],
        "resource_types": ["document", "selection", "file", "project"],
        "accepted_messages": ["send_resource"],
        "emitted_messages": ["export_vector", "send_resource"],
        "permissions": ["read_resource", "write_resource", "reference_resource", "send_message", "launch_universe"],
    },
    {
        "id":           "stardust",
        "manifest_path": str(_app_dir("stardust") / "existence-manifest.json"),
        "name":         "StarDust",
        "description":  "Univers-atelier : conception, test, validation et publication des outils utilisés par les autres univers.",
        "category":     "Création",
        "icon_emoji":   "✧",
        "icon_path":    "",
        "accent_color": "#A78BFA",
        "version":      "26.0",
        "installed":    True,
        "exec_path":    _launcher("stardust") or _python(),
        "exec_args":    [] if _launcher("stardust") else [str(_app_dir("stardust") / "main.py")],
        "working_dir":  str(_app_dir("stardust")),
        "install_type": "manual",
        "install_script": "",
        "git_url":      "",
        "tags":         ["stardust", "creator", "atelier", "fusion", "brush", "univers"],
        "app_kind":     "universe",
        "embedding_mode": "embeddable_view",
        "view_protocol": "existence.view.v1",
        "capabilities": ["creator_host", "fusion_creator", "brush_engine_creator", "resource_authoring", "resource_validation", "stardust_core_native"],
        "resource_types": ["brush_engine", "blend_definition", "blend_result", "palette", "gradient", "module", "project"],
        "accepted_messages": ["resource", "resource_bundle", "blend_definition", "blend_result"],
        "emitted_messages": ["resource", "resource_bundle", "blend_definition", "blend_result"],
        "permissions": ["read_resource", "write_resource", "reference_resource", "send_message", "launch_universe"],
        "resource_bindings": [
            {"consumer": "stardust", "access": "read_write"},
            {"consumer": "nebula", "access": "reference"},
            {"consumer": "atlas", "access": "reference"},
        ],
    },
    {
        "id": "fusion_creator", "name": "Créateur de fusion",
        "description": "Module de fusion avancée branchable sur StarDust pour construire des définitions de fusion.",
        "category": "Création", "icon_emoji": "◈", "icon_path": "",
        "accent_color": "#F472B6", "version": "26.0", "installed": True,
        "exec_path": "", "exec_args": [], "working_dir": "", "install_type": "system",
        "install_script": "", "git_url": "", "tags": ["nebula", "fusion", "module"],
        "orbit_of": "stardust", "app_kind": "orbital_module",
        "capabilities": ["fusion_creator", "layer_blending"],
        "resource_types": ["image", "project"],
        "accepted_messages": ["send_resource"], "emitted_messages": [],
        "orbit_relation": "available_from",
    },
    {
        "id": "palette_creator", "name": "Palette Creator",
        "description": "Module de création de palettes (nuanciers, harmonies, extraction depuis une image). Branché sur StarDust, il y apporte son interface.",
        "category": "Création", "icon_emoji": "◐", "icon_path": "",
        "accent_color": "#F59E0B", "version": "26.0", "installed": True,
        "exec_path": "", "exec_args": [], "working_dir": "", "install_type": "system",
        "install_script": "", "git_url": "", "tags": ["stardust", "palette", "couleur", "module"],
        "orbit_of": "stardust", "app_kind": "orbital_module",
        "capabilities": ["palette_creator", "creator_interface"],
        "resource_types": ["palette"],
        "accepted_messages": ["send_resource"], "emitted_messages": ["resource"],
        "orbit_relation": "available_from",
    },
    {
        "id": "gradient_creator", "name": "Gradient Creator",
        "description": "Module de création de dégradés (arrêts, interpolation OKLab, aperçus linéaire/radial/conique). Branché sur StarDust, il y apporte son interface.",
        "category": "Création", "icon_emoji": "◑", "icon_path": "",
        "accent_color": "#22D3EE", "version": "26.0", "installed": True,
        "exec_path": "", "exec_args": [], "working_dir": "", "install_type": "system",
        "install_script": "", "git_url": "", "tags": ["stardust", "dégradé", "gradient", "module"],
        "orbit_of": "stardust", "app_kind": "orbital_module",
        "capabilities": ["gradient_creator", "creator_interface"],
        "resource_types": ["gradient"],
        "accepted_messages": ["send_resource"], "emitted_messages": ["resource"],
        "orbit_relation": "available_from",
    },
    {
        "id": "pixel_art", "name": "Pixel Art",
        "description": "Module pixel art pour Nebula : crayon pixel-perfect, palettes verrouillées, tramage, grilles, tuiles en boucle et export net ×N / PNG indexé.",
        "category": "Création", "icon_emoji": "▦", "icon_path": "",
        "accent_color": "#34D399", "version": "26.0", "installed": True,
        "exec_path": "", "exec_args": [], "working_dir": "", "install_type": "system",
        "install_script": "", "git_url": "", "tags": ["nebula", "pixel", "module"],
        "orbit_of": "nebula", "app_kind": "orbital_module",
        "capabilities": ["pixel_art", "palette_lock", "tile_mode"],
        "resource_types": ["image", "palette"],
        "accepted_messages": ["send_resource"], "emitted_messages": [],
        "orbit_relation": "available_from",
    },
    {
        "id": "nova", "name": "Nova",
        "manifest_path": str(_app_dir("nova") / "existence-manifest.json"),
        "description": "Développement photo façon Camera Raw × Lightroom : RAW/JPEG, réglages non destructifs, export. Autonome ou module de Nebula.",
        "category": "Création", "icon_emoji": "✺", "icon_path": "",
        "accent_color": "#FBBF24", "version": "26.0", "installed": True,
        "exec_path": _launcher("nova") or _python(), "exec_args": [] if _launcher("nova") else ["main.py"], "working_dir": str(_app_dir("nova")),
        "install_type": "manual", "install_script": "", "git_url": "",
        "tags": ["photo", "raw", "développement", "nebula"],
        "orbit_of": "nebula", "app_kind": "orbital_module",
        "capabilities": ["raw_development", "photo_library", "resource_transformation", "wormhole_live"],
        "resource_types": ["image", "raw", "preset"],
        "accepted_messages": ["process_resource", "send_resource"],
        "emitted_messages": ["send_resource"],
        "permissions": ["read_resource", "write_resource", "reference_resource", "send_message"],
        "orbit_relation": "available_from",
    },
    {
        "id": "resource_center", "name": "Resources",
        "description": "Capacité Existence de consultation, import et circulation des ressources partagées.",
        "category": "Utilitaires", "icon_emoji": "▦", "icon_path": "",
        "accent_color": "#06B6D4", "version": "26.0", "installed": True,
        "exec_path": "", "exec_args": [], "working_dir": "", "install_type": "system",
        "install_script": "", "git_url": "", "tags": ["existence", "resources", "module"],
        "orbit_of": "existence", "app_kind": "service",
        "capabilities": ["resource_store", "resource_provider", "resource_consumer"],
        "resource_types": [
            "documents", "images", "projects", "brushes", "brush_engines", "blends",
            "filters", "effects", "masks", "generators", "fonts", "icc_profiles",
            "libraries", "modules", "textures", "patterns", "gradients", "palettes",
            "styles", "reference_sets",
        ],
        "accepted_messages": ["resource", "resource_bundle", "blend_definition", "blend_result"],
        "emitted_messages": ["resource", "resource_bundle", "blend_definition", "blend_result"],
        "orbit_relation": "shared_service",
        "resource_bindings": [
            {"consumer": "nebula", "access": "read_write"},
            {"consumer": "atlas", "access": "reference"},
            {"consumer": "cosmos", "access": "reference"},
            {"consumer": "singularity", "access": "read_write"},
        ],
    },
    {
        "id": "singularity", "name": "Singularity",
        "manifest_path": str(_app_dir("singularity") / "existence-manifest.json"),
        "description": "Univers de traitements et transformations pour les ressources produites ailleurs.",
        "category": "Utilitaires", "icon_emoji": "◉", "icon_path": "",
        "accent_color": "#FFB45B", "version": "26.0", "installed": True,
        "exec_path": _launcher("singularity") or _python(), "exec_args": [] if _launcher("singularity") else ["webready.py"], "working_dir": str(_app_dir("singularity")), "install_type": "manual",
        "install_script": "", "git_url": "", "tags": ["outil", "nebula", "création"],
        "orbit_of": "nebula",
        "app_kind": "orbital_module",
        "capabilities": ["image_processing", "resource_transformation", "receive_nebula_resource"],
        "resource_types": ["image", "file", "project"],
        "accepted_messages": ["process_resource", "send_resource"],
        "emitted_messages": ["send_resource"],
        "permissions": ["read_resource", "write_resource", "reference_resource", "send_message"],
        "orbit_relation": "available_from",
    },
]

for _default_app in DEFAULT_APPS:
    normalize_contract(_default_app)

SYSTEM_APP_IDS = {app["id"] for app in DEFAULT_APPS if app.get("system_role")}


# ══════════════════════════════════════════════════════════════
#  CONFIG MANAGER
# ══════════════════════════════════════════════════════════════

class ConfigManager:
    def __init__(self):
        self.last_error = ""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            # Récupère le catalogue existant au premier lancement d'Existence.
            if LEGACY_CONFIG_FILE.exists():
                try:
                    with open(LEGACY_CONFIG_FILE, encoding="utf-8") as f:
                        self.save(json.load(f))
                except Exception:
                    self.save(DEFAULT_APPS)
            else:
                self.save(DEFAULT_APPS)

    def load(self) -> List[Dict]:
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                apps = json.load(f)
                migration_changed = False
                # Compatibilité ascendante : les anciennes configurations
                # peuvent encore appeler Fusion Creator "blend_creator".
                normalized_apps = []
                for app in apps if isinstance(apps, list) else []:
                    before = json.dumps(app, sort_keys=True, ensure_ascii=False) if isinstance(app, dict) else None
                    if isinstance(app, dict):
                        original_id = app.get("id")
                        normalize_app_identity(app)
                        # Lorsqu'un alias et son identifiant canonique
                        # coexistent, la fiche canonique doit être prioritaire.
                        app["_canonical_source"] = original_id
                    after = json.dumps(app, sort_keys=True, ensure_ascii=False) if isinstance(app, dict) else None
                    migration_changed = migration_changed or before != after
                    normalized_apps.append(app)
                normalized_apps.sort(key=lambda item: item.get("_canonical_source") != item.get("id")
                                    if isinstance(item, dict) else False)
                deduplicated = {}
                for app in normalized_apps:
                    if not isinstance(app, dict):
                        continue
                    app_id = app.get("id")
                    if app_id in deduplicated:
                        existing = deduplicated[app_id]
                        for key, value in app.items():
                            if key not in existing or existing.get(key) in (None, "", [], {}):
                                existing[key] = value
                        migration_changed = True
                    else:
                        deduplicated[app_id] = app
                apps = list(deduplicated.values())
                for app in apps:
                    app.pop("_canonical_source", None)
                # Les anciennes configurations sont enrichies sans absorber un
                # univers dans un autre : Atlas, Nebula et Cosmos restent autonomes.
                for app in apps:
                    if app.get("id") == "fusion_creator":
                        app.setdefault("orbit_of", "nebula")
                        app["app_kind"] = "orbital_module"
                    if (app.get("id") == "singularity" and not app.get("orbit_of")
                            and app.get("orbit_relation") not in {"detached", "toolbox", "standalone"}):
                        app["orbit_of"] = "nebula"
                        app["app_kind"] = "orbital_module"
                # Répare une ancienne manipulation qui pouvait créer une
                # boucle entre StarDust et son module de fusion. Une boucle
                # empêche le calcul récursif des positions et masque les deux
                # astres de la carte.
                by_id = {app.get("id"): app for app in apps}
                stardust = by_id.get("stardust")
                fusion_creator = by_id.get("fusion_creator")
                if (stardust and fusion_creator
                        and stardust.get("orbit_of") == "fusion_creator"):
                    stardust["orbit_of"] = ""
                    stardust["app_kind"] = "universe"
                    stardust["orbit_relation"] = "detached"
                    stardust["map_position"] = {}
                    fusion_creator["orbit_of"] = "stardust"
                    fusion_creator["app_kind"] = "orbital_module"
                    fusion_creator["orbit_relation"] = "available_from"
                    fusion_creator["map_position"] = {}
                # Les nouveaux outils conceptuels apparaissent sans toucher aux apps
                # personnelles déjà présentes dans le catalogue.
                known_ids = {app.get("id") for app in apps}
                for default_app in DEFAULT_APPS:
                    if default_app["id"] not in known_ids:
                        apps.append(dict(default_app))
                for app in apps:
                    default = next((a for a in DEFAULT_APPS if a["id"] == app.get("id")), None)
                    if not default:
                        continue
                    if app.get("id") == "resource_center" and (
                            not app.get("orbit_of") or app.get("app_kind") != "service"):
                        # Ressources est un service commun d'Existence : un
                        # passage par le Void l'avait rendu impossible à rattacher.
                        app["orbit_of"] = "existence"
                        app["app_kind"] = "service"
                        app["orbit_relation"] = "shared_service"
                        app["map_position"] = {}
                    if (app.get("id") == "fusion_creator" and not module_hosts(app)
                            and app.get("orbit_relation") != "toolbox"):
                        # Fusion Creator sans hôte (passage par le Void) :
                        # il retrouve StarDust. Rangé dans la boîte à
                        # outils ou branché ailleurs, on respecte ce choix.
                        set_module_hosts(app, ["stardust"])
                        app["app_kind"] = "orbital_module"
                        app["orbit_relation"] = "available_from"
                    # Chemins périmés (dossier renommé, app passée en paquet) :
                    # on reprend ceux calculés par existence_paths.
                    stale_dir = app.get("working_dir") and not Path(app["working_dir"]).exists()
                    stale_exec = (str(app.get("exec_path", "")).startswith("/")
                                  and not Path(app["exec_path"]).exists())
                    if (stale_dir or stale_exec) and default.get("working_dir", "") != app.get("working_dir"):
                        for key in ("exec_path", "exec_args", "working_dir", "manifest_path", "manifest_command"):
                            if key in default:
                                app[key] = list(default[key]) if isinstance(default[key], list) else default[key]
                        migration_changed = True
                    if app.get("exec_path") in {"python", "python3"} and _python() not in {"python", "python3"}:
                        app["exec_path"] = _python()
                        migration_changed = True
                    if not is_release_version(app.get("version")):
                        # Schéma <année>.<release> : 26.0 = première release 2026.
                        app["version"] = default.get("version", APP_VERSION)
                        migration_changed = True
                    if not is_release_version(app.get("existence_min_version")):
                        app["existence_min_version"] = APP_VERSION
                        migration_changed = True
                    app.setdefault("orbit_of", default.get("orbit_of", ""))
                    app.setdefault("system_role", default.get("system_role", ""))
                    app.setdefault("app_kind", default.get("app_kind", "universe"))
                    for field in ("capabilities", "resource_types", "accepted_messages", "emitted_messages", "embedding_mode", "view_protocol"):
                        if not app.get(field):
                            app[field] = list(default.get(field, []))
                    app.setdefault("orbit_relation", default.get("orbit_relation", ""))
                    app.setdefault("dependencies", default.get("dependencies", []))
                    if not app.get("permissions"):
                        app["permissions"] = list(default.get("permissions", []))
                    app.setdefault("existence_min_version", default.get("existence_min_version", APP_VERSION))
                    app.setdefault("working_dir", default.get("working_dir", ""))
                    app.setdefault("manifest_path", default.get("manifest_path", ""))
                    app.setdefault("manifest_command", default.get("manifest_command", []))
                    if app.get("id") in {"atlas", "nebula", "cosmos", "singularity"} and not app.get("exec_path"):
                        app["installed"] = default.get("installed", False)
                        app["exec_path"] = default.get("exec_path", "")
                        app["exec_args"] = list(default.get("exec_args", []))
                        app["working_dir"] = default.get("working_dir", "")
                    if app.get("id") == "atlas" and app.get("exec_path", "").endswith("/build/CreativeSystemAtlasGtk"):
                        app["exec_path"] = default.get("exec_path", "")
                    if app.get("id") == "cosmos" and app.get("exec_path", "").endswith("/Cosmos/start-desktop.sh"):
                        app["working_dir"] = default.get("working_dir", "")
                        app["installed"] = True
                    if (app.get("id") == "singularity" and Path(default.get("working_dir", "")).exists()
                            and app.get("orbit_relation") not in {"detached", "toolbox", "standalone"}
                            and not module_hosts(app)):
                        app["installed"] = default.get("installed", False)
                        app["exec_path"] = default.get("exec_path", "")
                        app["exec_args"] = list(default.get("exec_args", []))
                        app["working_dir"] = default.get("working_dir", "")
                        app["orbit_of"] = default.get("orbit_of", "nebula")
                        app["app_kind"] = default.get("app_kind", "orbital_module")
                        app["orbit_relation"] = default.get("orbit_relation", "available_from")
                    # Migration : ces univers possèdent désormais une vue
                    # Wayland fournie par Existence. Une ancienne configuration
                    # peut contenir le défaut historique "external".
                    if app.get("id") in {"atlas", "nebula", "cosmos"}:
                        app["embedding_mode"] = default.get("embedding_mode", "external")
                        app["view_protocol"] = default.get("view_protocol", "existence.view.v1")
                # Le manifest applicatif est la source de vérité pour
                # l'identité et les capacités déclarées. Le catalogue garde
                # uniquement l'état et la configuration possédés par Existence.
                for app in apps:
                    manifest_path = app.get("manifest_path")
                    manifest = load_manifest_file(manifest_path) if manifest_path else None
                    if manifest is None and app.get("manifest_command"):
                        manifest = load_manifest_command(app["manifest_command"])
                    if manifest is not None:
                        apply_manifest_to_catalog(app, manifest)
                for app in apps:
                    normalize_contract(app)
                    if app.get("resource_namespace"):
                        app["resource_namespace"] = canonical_resource_uri(app["resource_namespace"])
                if migration_changed:
                    self.save(apps)
                return apps
        except Exception:
            apps = [dict(a) for a in DEFAULT_APPS]
            for app in apps:
                normalize_contract(app)
            return apps

    def save(self, apps: List[Dict]) -> None:
        for app in apps:
            normalize_contract(app)
        try:
            atomic_write_json(CONFIG_FILE, apps)
            self.last_error = ""
        except OSError as exc:
            self.last_error = str(exc)


class AppReadiness:
    READY = "ready"
    INSTALLABLE = "installable"
    MISSING_EXEC = "missing_exec"
    BROKEN_EXEC = "broken_exec"
    SYSTEM = "system"


def is_app_installed(app_data: dict) -> bool:
    exec_path = app_data.get("exec_path", "").strip()
    if not app_data.get("installed") or not exec_path:
        return False
    path = Path(exec_path).expanduser()
    return path.exists() or shutil.which(exec_path) is not None


def verify_app_readiness(app_data: dict) -> Tuple[str, str]:
    """Retourne un statut court et une explication lisible pour l'utilisateur."""
    if is_module(app_data) and not app_data.get("exec_path"):
        return AppReadiness.SYSTEM, "Module disponible dans Existence ; aucun processus autonome requis."
    if app_data.get("system_role"):
        return AppReadiness.SYSTEM, "Module système prêt dans Existence."

    exec_path = app_data.get("exec_path", "").strip()
    install_script = app_data.get("install_script", "").strip()
    git_url = app_data.get("git_url", "").strip()

    if exec_path:
        path = Path(exec_path).expanduser()
        if is_app_installed(app_data):
            return AppReadiness.READY, "Installée."
        return AppReadiness.BROKEN_EXEC, f"Exécutable introuvable : {exec_path}"

    if install_script or git_url:
        return AppReadiness.INSTALLABLE, "Non installée. Source connue pour l'installateur."

    return AppReadiness.MISSING_EXEC, "Non installée. Aucune source d'installation configurée."


# ══════════════════════════════════════════════════════════════
#  STAR FIELD BACKGROUND
# ══════════════════════════════════════════════════════════════

class StarField(QWidget):
    """Fond étoilé animé avec nébuleuses."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._phase  = 0.0
        self._stars  = []
        self._nebulae = []
        self._generate()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)  # ~20 fps

    def _generate(self):
        rng = random.Random(1337)
        for _ in range(180):
            self._stars.append({
                "x":     rng.random(),
                "y":     rng.random(),
                "size":  rng.uniform(0.4, 2.4),
                "phase": rng.random() * math.pi * 2,
                "speed": rng.uniform(0.3, 1.6),
            })
        nebula_defs = [
            ("#7C3AED", 0.042), ("#06B6D4", 0.030), ("#D946EF", 0.026),
            ("#1D4ED8", 0.035), ("#7C3AED", 0.028), ("#0F766E", 0.024),
        ]
        for color, alpha in nebula_defs:
            self._nebulae.append({
                "x":     rng.uniform(0.05, 0.95),
                "y":     rng.uniform(0.05, 0.95),
                "rx":    rng.uniform(0.08, 0.24),
                "ry":    rng.uniform(0.06, 0.18),
                "color": color,
                "alpha": alpha,
            })

    def _tick(self):
        self._phase += 0.04
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Deep-space gradient
        grad = QLinearGradient(0, 0, w * 0.7, h)
        grad.setColorAt(0.0, QColor("#050512"))
        grad.setColorAt(0.4, QColor("#08081A"))
        grad.setColorAt(1.0, QColor("#060614"))
        p.fillRect(0, 0, w, h, grad)

        # ── Nebulae
        for n in self._nebulae:
            cx, cy = n["x"] * w, n["y"] * h
            rx, ry = n["rx"] * w, n["ry"] * h
            rg = QRadialGradient(QPointF(cx, cy), max(rx, ry))
            c0 = QColor(n["color"]); c0.setAlphaF(n["alpha"])
            c1 = QColor(n["color"]); c1.setAlphaF(n["alpha"] * 0.4)
            c2 = QColor(n["color"]); c2.setAlphaF(0.0)
            rg.setColorAt(0.0, c0)
            rg.setColorAt(0.5, c1)
            rg.setColorAt(1.0, c2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(rg))
            p.drawEllipse(QRectF(cx - rx, cy - ry, rx * 2, ry * 2))

        # ── Stars
        for star in self._stars:
            b = 0.45 + 0.55 * math.sin(self._phase * star["speed"] + star["phase"])
            alpha = int(b * 220 + 35)
            rv = int(200 + b * 55)
            color = QColor(rv, rv, 255, alpha)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            sx, sy = star["x"] * w, star["y"] * h
            size = star["size"] * (0.7 + 0.3 * b)
            p.drawEllipse(QRectF(sx - size / 2, sy - size / 2, size, size))
            if star["size"] > 1.5 and b > 0.7:
                glow = QColor(180, 180, 255, int(alpha * 0.12))
                p.setBrush(glow)
                p.drawEllipse(QRectF(sx - size * 2, sy - size * 2, size * 4, size * 4))

        p.end()


# ══════════════════════════════════════════════════════════════
#  APP ICON WIDGET
# ══════════════════════════════════════════════════════════════

class AppIconWidget(QLabel):
    """Cercle coloré avec emoji centré."""

    def __init__(self, emoji: str = "📦", color: str = "#7C3AED", size: int = 54, parent=None):
        super().__init__(parent)
        self.emoji  = emoji
        self.accent = QColor(color)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(); f.setPointSize(size // 3)
        self.setFont(f)
        self.setText(emoji)

    def set_accent(self, color: str):
        self.accent = QColor(color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bg = QColor(self.accent); bg.setAlphaF(0.14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawEllipse(2, 2, w - 4, h - 4)
        border = QColor(self.accent); border.setAlphaF(0.45)
        p.setPen(QPen(border, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(2, 2, w - 4, h - 4)
        p.end()
        super().paintEvent(event)


# ══════════════════════════════════════════════════════════════
#  APP CARD
# ══════════════════════════════════════════════════════════════

class AppCard(QFrame):
    """Carte d'application avec launch / configure / menu contextuel."""

    launch_requested   = Signal(dict)
    edit_requested     = Signal(dict)
    remove_requested   = Signal(str)
    install_requested  = Signal(dict)

    CARD_W = 260
    CARD_H = 200

    def __init__(self, app_data: dict, parent=None):
        super().__init__(parent)
        self.app_data = app_data
        self._hovered = False
        self._build_ui()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda _: self._show_menu())

    # ── helpers
    @staticmethod
    def _lighten(hex_c: str, amt: int = 22) -> str:
        c = QColor(hex_c); h, s, l, a = c.getHsl()
        return QColor.fromHsl(h, s, min(255, l + amt), a).name()

    @staticmethod
    def _darken(hex_c: str, amt: int = 22) -> str:
        c = QColor(hex_c); h, s, l, a = c.getHsl()
        return QColor.fromHsl(h, s, max(0, l - amt), a).name()

    def _build_ui(self):
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("AppCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 14, 14)
        layout.setSpacing(6)

        # ── Header row
        hdr = QHBoxLayout(); hdr.setSpacing(12)

        accent = self.app_data.get("accent_color", C["purple"])
        self.icon_w = AppIconWidget(self.app_data.get("icon_emoji", "📦"), accent, 52)
        hdr.addWidget(self.icon_w)

        meta_col = QVBoxLayout(); meta_col.setSpacing(2)
        self.name_lbl = QLabel(self.app_data["name"])
        self.name_lbl.setFont(QFont("", 15, QFont.Weight.Bold))
        self.name_lbl.setStyleSheet(f"color:{C['text']};background:transparent;")
        meta_col.addWidget(self.name_lbl)

        meta_row = QHBoxLayout(); meta_row.setSpacing(8)
        ver_lbl = QLabel(display_version(self.app_data))
        ver_lbl.setStyleSheet(f"color:{C['text3']};background:transparent;font-size:10px;")
        meta_row.addWidget(ver_lbl)
        cat_lbl = QLabel(self.app_data.get("category", ""))
        cat_lbl.setStyleSheet(f"color:{accent};background:transparent;font-size:10px;font-weight:600;")
        meta_row.addWidget(cat_lbl)
        meta_row.addStretch()
        meta_col.addLayout(meta_row)
        hdr.addLayout(meta_col)
        hdr.addStretch()

        # ⋯ button
        self.menu_btn = QToolButton()
        self.menu_btn.setText("⋯")
        self.menu_btn.setFixedSize(26, 26)
        self.menu_btn.setStyleSheet(f"""
            QToolButton{{color:{C['text3']};background:transparent;border:none;font-size:14px;border-radius:5px;}}
            QToolButton:hover{{color:{C['text2']};background:{C['border']};}}
        """)
        self.menu_btn.clicked.connect(self._show_menu)
        hdr.addWidget(self.menu_btn, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addLayout(hdr)

        # ── Description
        self.desc_lbl = QLabel(self.app_data.get("description", ""))
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet(f"color:{C['text2']};background:transparent;font-size:11px;")
        self.desc_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.desc_lbl.setMaximumHeight(38)
        layout.addWidget(self.desc_lbl)
        layout.addStretch()

        # ── Action button
        self.action_btn = QPushButton()
        self.action_btn.setFixedHeight(34)
        self.action_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._update_action_btn()
        layout.addWidget(self.action_btn)

        self._update_frame_style()

    def _update_action_btn(self):
        accent = self.app_data.get("accent_color", C["purple"])
        is_installed = self.app_data.get("installed") and self.app_data.get("exec_path")

        try:
            self.action_btn.clicked.disconnect()
        except Exception:
            pass

        if is_installed:
            self.action_btn.setText("▶  Lancer")
            self.action_btn.setStyleSheet(f"""
                QPushButton{{background:{accent};color:white;border:none;border-radius:8px;
                             font-size:12px;font-weight:700;}}
                QPushButton:hover{{background:{self._lighten(accent)};}}
                QPushButton:pressed{{background:{self._darken(accent)};}}
            """)
            self.action_btn.clicked.connect(lambda: self.launch_requested.emit(self.app_data))
        else:
            self.action_btn.setText("⚙  Configurer")
            self.action_btn.setStyleSheet(f"""
                QPushButton{{background:{C['surface_h']};color:{C['text2']};border:1px solid {C['border']};
                             border-radius:8px;font-size:12px;font-weight:600;}}
                QPushButton:hover{{background:{C['border']};color:{C['text']};border-color:{C['border_h']};}}
            """)
            self.action_btn.clicked.connect(lambda: self.install_requested.emit(self.app_data))

    def _update_frame_style(self):
        accent = self.app_data.get("accent_color", C["purple"])
        border = C["border_h"] if self._hovered else C["border"]
        self.setStyleSheet(f"""
            QFrame#AppCard{{
                background:{C['surface']};
                border:1px solid {border};
                border-radius:16px;
                border-top:2px solid {accent};
            }}
        """)

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu{{background:{C['surface_h']};border:1px solid {C['border']};
                   border-radius:10px;padding:4px;color:{C['text']};}}
            QMenu::item{{padding:8px 18px;border-radius:6px;font-size:12px;}}
            QMenu::item:selected{{background:{C['border']};}}
            QMenu::separator{{height:1px;background:{C['border']};margin:4px 8px;}}
        """)
        edit_a   = menu.addAction("✏️   Modifier")
        menu.addSeparator()
        remove_a = menu.addAction("🗑️   Supprimer")

        action = menu.exec(QCursor.pos())
        if action == edit_a:
            self.edit_requested.emit(self.app_data)
        elif action == remove_a:
            self.remove_requested.emit(self.app_data["id"])

    def update_data(self, new_data: dict):
        self.app_data = new_data
        accent = new_data.get("accent_color", C["purple"])
        self.icon_w.emoji = new_data.get("icon_emoji", "📦")
        self.icon_w.set_accent(accent)
        self.icon_w.setText(new_data.get("icon_emoji", "📦"))
        self.name_lbl.setText(new_data["name"])
        self.desc_lbl.setText(new_data.get("description", ""))
        self._update_action_btn()
        self._update_frame_style()

    def enterEvent(self, event):
        self._hovered = True
        self._update_frame_style()
        sh = QGraphicsDropShadowEffect()
        sh.setBlurRadius(22)
        glow = QColor(self.app_data.get("accent_color", C["purple"]))
        glow.setAlphaF(0.35)
        sh.setColor(glow)
        sh.setOffset(0, 5)
        self.setGraphicsEffect(sh)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_frame_style()
        self.setGraphicsEffect(None)
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.app_data.get("installed") and self.app_data.get("exec_path"):
            self.launch_requested.emit(self.app_data)


# ══════════════════════════════════════════════════════════════
#  ADD / EDIT DIALOG
# ══════════════════════════════════════════════════════════════

class AppDialog(QDialog):
    """Dialogue d'ajout ou de modification d'application."""

    def __init__(self, app_data: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.app_data     = dict(app_data) if app_data else None
        self.is_edit      = app_data is not None
        self._color       = (app_data or {}).get("accent_color", C["purple"])
        self._drag_pos    = QPoint(0, 0)
        self.result_data  = {}
        self._build_ui()

    def _build_ui(self):
        title_str = "Modifier l'application" if self.is_edit else "Ajouter une application"
        self.setWindowTitle(title_str)
        self.setFixedSize(520, 690)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog{{background:{C['bg2']};border:1px solid {C['border_h']};border-radius:16px;}}
            QLabel{{color:{C['text2']};font-size:12px;background:transparent;}}
            QLineEdit,QComboBox,QTextEdit{{
                background:{C['surface']};border:1px solid {C['border']};border-radius:8px;
                color:{C['text']};padding:7px 12px;font-size:12px;
            }}
            QLineEdit:focus,QComboBox:focus,QTextEdit:focus{{border-color:{C['purple']};}}
            QComboBox::drop-down{{border:none;padding-right:8px;}}
            QComboBox QAbstractItemView{{
                background:{C['surface_h']};border:1px solid {C['border']};
                color:{C['text']};selection-background-color:{C['border']};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(0)

        # ── Title bar
        tbar = QHBoxLayout()
        tlbl = QLabel(title_str)
        tlbl.setStyleSheet(f"color:{C['text']};font-size:16px;font-weight:700;")
        tbar.addWidget(tlbl)
        tbar.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{C['text3']};border:none;font-size:13px;border-radius:6px;}}
            QPushButton:hover{{background:{C['red']};color:white;}}
        """)
        close_btn.clicked.connect(self.reject)
        tbar.addWidget(close_btn)
        root.addLayout(tbar)
        root.addSpacing(18)

        def lbl(txt):
            l = QLabel(txt)
            l.setStyleSheet(
                f"color:{C['text3']};font-size:9px;font-weight:700;"
                "letter-spacing:1.5px;text-transform:uppercase;")
            return l

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setContentsMargins(0, 0, 0, 0)

        # Nom
        self.name_e = QLineEdit((self.app_data or {}).get("name", ""))
        self.name_e.setPlaceholderText("Ex: Atlas")
        form.addRow(lbl("Nom *"), self.name_e)

        # Description
        self.desc_e = QTextEdit((self.app_data or {}).get("description", ""))
        self.desc_e.setPlaceholderText("Description courte…")
        self.desc_e.setFixedHeight(62)
        form.addRow(lbl("Description"), self.desc_e)

        # Catégorie
        self.cat_cb = QComboBox()
        for cat in CATEGORIES[1:]:
            self.cat_cb.addItem(cat)
        if self.is_edit:
            idx = self.cat_cb.findText(self.app_data.get("category", "Autres"))
            if idx >= 0:
                self.cat_cb.setCurrentIndex(idx)
        form.addRow(lbl("Catégorie"), self.cat_cb)

        # Icône emoji + couleur
        ic_row = QHBoxLayout(); ic_row.setSpacing(10)
        self.emoji_e = QLineEdit((self.app_data or {}).get("icon_emoji", "📦"))
        self.emoji_e.setFixedWidth(78)
        self.emoji_e.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emoji_e.setStyleSheet(
            self.emoji_e.styleSheet() + "font-size:20px;")
        ic_row.addWidget(self.emoji_e)
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(78, 36)
        self._refresh_color_btn()
        self.color_btn.clicked.connect(self._pick_color)
        ic_row.addWidget(self.color_btn)
        ic_row.addStretch()
        form.addRow(lbl("Icône / Couleur"), ic_row)

        # Version
        self.ver_e = QLineEdit((self.app_data or {}).get("version", APP_VERSION))
        form.addRow(lbl("Version"), self.ver_e)

        # Exécutable
        exec_row = QHBoxLayout(); exec_row.setSpacing(8)
        self.exec_e = QLineEdit((self.app_data or {}).get("exec_path", ""))
        self.exec_e.setPlaceholderText("Chemin vers l'exécutable (optionnel)")
        exec_row.addWidget(self.exec_e)
        browse = QPushButton("📂")
        browse.setFixedSize(36, 36)
        browse.setStyleSheet(f"""
            QPushButton{{background:{C['surface_h']};border:1px solid {C['border']};border-radius:8px;color:{C['text']};}}
            QPushButton:hover{{background:{C['border']};}}
        """)
        browse.clicked.connect(self._browse_exec)
        exec_row.addWidget(browse)
        form.addRow(lbl("Exécutable"), exec_row)

        # Dossier de travail
        self.cwd_e = QLineEdit((self.app_data or {}).get("working_dir", ""))
        self.cwd_e.setPlaceholderText("Dossier depuis lequel lancer l'app (optionnel)")
        form.addRow(lbl("Dossier travail"), self.cwd_e)

        # Git URL
        self.git_e = QLineEdit((self.app_data or {}).get("git_url", ""))
        self.git_e.setPlaceholderText("https://github.com/toi/monapp.git")
        form.addRow(lbl("Git URL"), self.git_e)

        # Script d'installation
        self.install_e = QLineEdit((self.app_data or {}).get("install_script", ""))
        self.install_e.setPlaceholderText("Chemin vers un script d'installation (optionnel)")
        form.addRow(lbl("Script install"), self.install_e)

        # Orbite
        self.orbit_e = QLineEdit((self.app_data or {}).get("orbit_of", ""))
        self.orbit_e.setPlaceholderText("id de l'univers parent, ex: existence ou nebula")
        form.addRow(lbl("Orbite autour de"), self.orbit_e)

        root.addLayout(form)
        root.addStretch()

        # ── Boutons
        btn_row = QHBoxLayout(); btn_row.setSpacing(10); btn_row.addStretch()
        cancel = QPushButton("Annuler")
        cancel.setFixedHeight(38); cancel.setMinimumWidth(100)
        cancel.setStyleSheet(f"""
            QPushButton{{background:{C['surface_h']};color:{C['text2']};border:1px solid {C['border']};
                         border-radius:8px;font-size:12px;}}
            QPushButton:hover{{background:{C['border']};color:{C['text']};}}
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save_lbl = "Enregistrer" if self.is_edit else "Ajouter  +"
        save = QPushButton(save_lbl)
        save.setFixedHeight(38); save.setMinimumWidth(120)
        save.setStyleSheet(f"""
            QPushButton{{background:{C['purple']};color:white;border:none;border-radius:8px;
                         font-size:12px;font-weight:700;}}
            QPushButton:hover{{background:{C['purple_l']};}}
        """)
        save.clicked.connect(self._save)
        btn_row.addWidget(save)
        root.addLayout(btn_row)

    # ── internals
    def _refresh_color_btn(self):
        self.color_btn.setStyleSheet(f"""
            QPushButton{{background:{self._color};border:2px solid {C['border_h']};border-radius:8px;}}
            QPushButton:hover{{border-color:{C['text2']};}}
        """)
        self.color_btn.setText("")

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Choisir une couleur")
        if c.isValid():
            self._color = c.name()
            self._refresh_color_btn()

    def _browse_exec(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner l'exécutable", str(Path.home()))
        if path:
            self.exec_e.setText(path)

    def _save(self):
        name = self.name_e.text().strip()
        if not name:
            QMessageBox.warning(self, "Champ requis", "Le nom est obligatoire.")
            return
        exec_path = self.exec_e.text().strip()
        orbit_of = self.orbit_e.text().strip()
        self.result_data = {
            "id":             (self.app_data or {}).get("id") or str(uuid.uuid4())[:8],
            "name":           name,
            "description":    self.desc_e.toPlainText().strip(),
            "category":       self.cat_cb.currentText(),
            "icon_emoji":     self.emoji_e.text().strip() or "📦",
            "icon_path":      (self.app_data or {}).get("icon_path", ""),
            "accent_color":   self._color,
            "version":        self.ver_e.text().strip() or APP_VERSION,
            "installed":      bool(exec_path),
            "exec_path":      exec_path,
            "exec_args":      (self.app_data or {}).get("exec_args", []),
            "working_dir":    self.cwd_e.text().strip(),
            "install_type":   "manual",
            "install_script": self.install_e.text().strip(),
            "git_url":        self.git_e.text().strip(),
            "tags":           (self.app_data or {}).get("tags", []),
            "orbit_of":       orbit_of,
            "ecosystem_id":   (self.app_data or {}).get("ecosystem_id", ECOSYSTEM_ID),
            "app_kind":       (self.app_data or {}).get("app_kind") or ("orbital_module" if orbit_of else "universe"),
            "capabilities":   (self.app_data or {}).get("capabilities", []),
            "map_position":   (self.app_data or {}).get("map_position", {}),
        }
        if (self.app_data or {}).get("system_role"):
            self.result_data["system_role"] = self.app_data["system_role"]
        self.accept()

    # drag frameless
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)


# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════

class Sidebar(QWidget):
    category_changed  = Signal(str)
    structure_changed = Signal(str)
    add_app_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(222)
        self._btns: Dict[str, QPushButton] = {}
        self._structure_btns: Dict[str, QPushButton] = {}
        self._current = "Toutes"
        self._current_structure = "Toutes"
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"""
            Sidebar{{background:{C['bg2']};border-right:1px solid {C['border']};}}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Logo
        logo_frame = QFrame()
        logo_frame.setFixedHeight(66)
        logo_frame.setStyleSheet(f"background:transparent;border-bottom:1px solid {C['border']};")
        ll = QHBoxLayout(logo_frame)
        ll.setContentsMargins(18, 10, 18, 10)

        star = QLabel("✦")
        star.setStyleSheet(f"color:{C['purple_l']};font-size:22px;background:transparent;")
        ll.addWidget(star)

        nc = QVBoxLayout(); nc.setSpacing(1)
        t1 = QLabel("EXISTENCE")
        t1.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700;background:transparent;")
        t2 = QLabel("creative universe")
        t2.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;")
        nc.addWidget(t1); nc.addWidget(t2)
        ll.addLayout(nc); ll.addStretch()
        lay.addWidget(logo_frame)
        lay.addSpacing(14)

        sec = QLabel("CARTOGRAPHIE")
        sec.setStyleSheet(f"""
            color:{C['text3']};font-size:9px;font-weight:700;letter-spacing:1.5px;
            background:transparent;padding:0 18px;
        """)
        lay.addWidget(sec)
        lay.addSpacing(6)

        cat_icons = {
            "Toutes": "✦", "Création": "🎨", "Productivité": "📝",
            "Développement": "💻", "Utilitaires": "🔧", "Autres": "📦",
        }
        for cat in CATEGORIES:
            icon = cat_icons.get(cat, "•")
            btn = QPushButton(f"  {icon}  {cat}")
            btn.setFixedHeight(36)
            btn.setStyleSheet(self._btn_css(False))
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, c=cat: self._select(c, emit=True))
            self._btns[cat] = btn
            lay.addWidget(btn)

        lay.addSpacing(12)
        div_kind = QFrame(); div_kind.setFixedHeight(1)
        div_kind.setStyleSheet(f"background:{C['border']};")
        lay.addWidget(div_kind)
        lay.addSpacing(12)

        kind_sec = QLabel("STRUCTURE")
        kind_sec.setStyleSheet(f"""
            color:{C['text3']};font-size:9px;font-weight:700;letter-spacing:1.5px;
            background:transparent;padding:0 18px;
        """)
        lay.addWidget(kind_sec)
        lay.addSpacing(6)

        structure_icons = {
            "Toutes": "✦", "Univers": "●", "Modules": "◌",
            "Services": "≡", "Infrastructure": "◇",
        }
        for item in STRUCTURE_FILTERS:
            icon = structure_icons.get(item, "•")
            btn = QPushButton(f"  {icon}  {item}")
            btn.setFixedHeight(32)
            btn.setStyleSheet(self._btn_css(False, compact=True))
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, k=item: self._select_structure(k, emit=True))
            self._structure_btns[item] = btn
            lay.addWidget(btn)

        lay.addSpacing(14)
        div = QFrame(); div.setFixedHeight(1)
        div.setStyleSheet(f"background:{C['border']};")
        lay.addWidget(div)
        lay.addSpacing(12)

        add_btn = QPushButton("  + Créer un nouvel astre")
        add_btn.setFixedHeight(38)
        add_btn.setStyleSheet(f"""
            QPushButton{{background:{C['bg2']};color:{C['purple_l']};
                border:1px dashed {C['purple']};border-radius:8px;
                font-size:12px;font-weight:600;margin:0 12px;}}
            QPushButton:hover{{background:#16123a;border-color:{C['purple_l']};}}
        """)
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.clicked.connect(self.add_app_requested.emit)
        lay.addWidget(add_btn)
        lay.addStretch()

        ver = QLabel(f"v{APP_VERSION}")
        ver.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;padding:12px 18px;")
        lay.addWidget(ver)

        self._select("Toutes")
        self._select_structure("Toutes")

    def _btn_css(self, active: bool, compact: bool = False) -> str:
        height_font = 12 if compact else 13
        if active:
            return f"""
                QPushButton{{background:#16123a;color:{C['purple_l']};border:none;
                    border-left:3px solid {C['purple']};border-radius:0;text-align:left;
                    padding-left:17px;font-size:{height_font}px;font-weight:600;}}
            """
        return f"""
            QPushButton{{background:transparent;color:{C['text2']};border:none;
                border-left:3px solid transparent;border-radius:0;text-align:left;
                padding-left:17px;font-size:{height_font}px;}}
            QPushButton:hover{{
                background:{C['surface_h']};
                color:{C['text']};
                border:none;
                border-left:3px solid {C['purple']};
                border-radius:0;
                text-align:left;
                padding-left:17px;
                font-size:{height_font}px;
            }}
        """

    def _select(self, cat: str, emit: bool = False):
        if self._current in self._btns:
            self._btns[self._current].setStyleSheet(self._btn_css(False))
        self._current = cat
        if cat in self._btns:
            self._btns[cat].setStyleSheet(self._btn_css(True))
        if emit:
            self.category_changed.emit(cat)

    def _select_structure(self, item: str, emit: bool = False):
        if self._current_structure in self._structure_btns:
            self._structure_btns[self._current_structure].setStyleSheet(self._btn_css(False, compact=True))
        self._current_structure = item
        if item in self._structure_btns:
            self._structure_btns[item].setStyleSheet(self._btn_css(True, compact=True))
        if emit:
            self.structure_changed.emit(item)


# ══════════════════════════════════════════════════════════════
#  ORBITAL MAP / CONTENT AREA
# ══════════════════════════════════════════════════════════════

class OrbitMap(QWidget):
    """Carte vivante d'Existence : les univers sont des astres, les outils gravitent."""
    app_selected = Signal(dict)
    app_activated = Signal(dict)
    app_moved = Signal(str, float, float)
    app_orbit_changed = Signal(str, str)
    module_plug = Signal(str, str, str, bool)  # module, hôte d'origine, cible, déplacer
    module_free = Signal(str, bool)            # module hybride : astre autonome oui/non
    wormhole_request = Signal(str, str)        # Alt+glisser d'une app vers une autre

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.apps, self.nodes, self.hovered, self.phase = [], {}, None, 0.0
        self.orbit_radii = {}
        self.dragging_id = None
        self.drag_offset = QPointF(0, 0)
        self.drag_start_pos = QPointF(0, 0)
        self._drag_started = False
        self._suppress_next_double_click = False
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.start(32)

    def showEvent(self, event):
        # Certains compositeurs suspendent un timer créé avant le premier
        # affichage ; le redémarrer ici rend l'orbite fiable dès l'ouverture.
        self.timer.start(32)
        super().showEvent(event)

    def set_apps(self, apps):
        self.apps = apps
        self.hovered = None
        self.update()

    def _visual_radius(self, app: dict) -> int:
        kind = app.get("app_kind", "")
        if on_map_free(app):
            return 46
        role = app.get("system_role", "")
        if kind == "environment":
            return 44
        if kind == "universe":
            return 64
        if kind == "orbital_module":
            return 16
        if kind == "service":
            return 14 if role in {"gravity", "wormholes", "resource_index", "common_services"} else 13
        return 15

    def _draw_universe(self, painter: QPainter, app: dict, x: float, y: float,
                       radius: float, selected: bool, color: QColor) -> None:
        """Dessine un monde identifiable plutôt qu'un simple nœud sphérique."""
        ident = app.get("id", "")
        painter.save()
        # Atmosphère et anneau orbital : la silhouette dépasse clairement
        # celle des modules et services.
        atmosphere = QColor(color)
        atmosphere.setAlpha(80 if selected else 48)
        painter.setPen(QPen(atmosphere, 2 if selected else 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(x - radius - 8, y - radius - 8,
                                   2 * (radius + 8), 2 * (radius + 8)))
        if ident in {"stardust", "atlas"}:
            ring = QColor(color); ring.setAlpha(95 if selected else 55)
            painter.setPen(QPen(ring, 2))
            painter.drawEllipse(QRectF(x - radius * 1.45, y - radius * .30,
                                       radius * 2.9, radius * .60))

        globe = QPainterPath()
        globe.addEllipse(QRectF(x - radius, y - radius, 2 * radius, 2 * radius))
        painter.setClipPath(globe)
        gradient = QRadialGradient(QPointF(x - radius * .30, y - radius * .38), radius * 1.35)
        highlight = QColor("#FFFFFF"); highlight.setAlpha(220)
        deep = color.darker(230); deep.setAlpha(255)
        gradient.setColorAt(0.0, highlight)
        gradient.setColorAt(0.14, color.lighter(145))
        gradient.setColorAt(0.62, color)
        gradient.setColorAt(1.0, deep)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QRectF(x - radius, y - radius, 2 * radius, 2 * radius))

        # Texture propre à chaque univers : carte, nébuleuse, constellation
        # ou atelier stellaire. Ces marques restent décoratives et ne gênent
        # pas la zone de clic du nœud.
        texture = QColor("#FFFFFF"); texture.setAlpha(38 if not selected else 60)
        painter.setPen(QPen(texture, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if ident == "atlas":
            for offset in (-.48, -.16, .16, .48):
                painter.drawArc(QRectF(x - radius * 1.1, y - radius * .7,
                                       radius * 2.2, radius * 1.4), int(offset * 180), 70 * 16)
            painter.setBrush(QBrush(QColor(190, 245, 215, 70)))
            painter.drawEllipse(QRectF(x - radius * .48, y - radius * .18,
                                       radius * .50, radius * .28))
            painter.drawEllipse(QRectF(x + radius * .16, y + radius * .05,
                                       radius * .32, radius * .22))
        elif ident == "cosmos":
            for offset in (-.48, 0.0, .48):
                painter.drawEllipse(QRectF(x - radius * .9, y + offset * radius,
                                           radius * 1.8, radius * .48))
            painter.setPen(QPen(QColor("#FFFFFF",), 2))
            for dx, dy in ((-.42, -.22), (.12, -.40), (.35, .18), (-.12, .42)):
                painter.drawPoint(QPointF(x + dx * radius, y + dy * radius))
        elif ident == "nebula":
            cloud = QColor("#FFB8EF"); cloud.setAlpha(70)
            painter.setBrush(QBrush(cloud)); painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(x - radius * .70, y - radius * .10, radius * 1.0, radius * .42))
            painter.drawEllipse(QRectF(x + radius * .02, y - radius * .48, radius * .65, radius * .55))
            painter.setPen(QPen(QColor("#FFFFFF",), 2))
            for dx, dy in ((-.55, -.45), (.48, -.30), (.22, .42), (-.25, .30)):
                painter.drawPoint(QPointF(x + dx * radius, y + dy * radius))
        else:
            painter.setPen(QPen(texture, 1))
            for dx, dy in ((-.46, -.25), (-.12, .38), (.28, -.12), (.48, .30), (.05, -.48)):
                painter.drawEllipse(QRectF(x + dx * radius, y + dy * radius, 4, 4))
        painter.restore()
        painter.setPen(QPen(color.lighter(165), 2 if selected else 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(x - radius, y - radius, 2 * radius, 2 * radius))

    def _tick(self):
        # Une rotation complète doit rester perceptible (~20 s), même sur une
        # carte peu chargée. La phase est bornée pour éviter sa dérive.
        self.phase = (self.phase + .010) % (math.pi * 2)
        if not self.dragging_id:
            self.update()

    def _manual_position(self, app: dict, w: int, h: int) -> Optional[Tuple[float, float]]:
        pos = app.get("map_position") or {}
        try:
            x = float(pos.get("x"))
            y = float(pos.get("y"))
        except (TypeError, ValueError):
            return None
        return (max(32, min(w - 32, x * w)), max(32, min(h - 32, y * h)))

    def _apply_manual_position(self, app: dict, nodes: dict, w: int, h: int) -> None:
        # Un astre en orbite reste soumis à la gravitation ; une ancienne
        # position de drag ne doit jamais le transformer en point immobile.
        if app.get("orbit_of") and not on_map_free(app):
            return
        manual = self._manual_position(app, w, h)
        if manual and app["id"] in nodes:
            _, _, r = nodes[app["id"]]
            nodes[app["id"]] = (manual[0], manual[1], r)

    # ── Boîte à outils : rangement des modules débranchés ──
    def _toolbox_rect(self) -> QRectF:
        w, h = max(1, self.width()), max(1, self.height())
        stored = [a for a in self.apps if in_toolbox(a)]
        width = max(230.0, 56.0 * len(stored) + 40.0)
        width = min(width, w * .60)
        return QRectF(18, h - 96, width, 78)

    def _layout_nodes(self):
        w, h = max(1, self.width()), max(1, self.height())
        stored = [a for a in self.apps if in_toolbox(a)]
        universes = [a for a in self.apps if (not a.get("orbit_of") or on_map_free(a)) and not in_toolbox(a)]
        tools = [a for a in self.apps if a.get("orbit_of")]
        nodes = {}
        orbit_radii = {}
        links = []  # (clé du corps, app, hôte)

        anchors = {
            "existence":   (0.58, 0.55),
            "nebula":      (0.34, 0.68),
            "atlas":       (0.73, 0.26),
            "cosmos":      (0.84, 0.62),
        }
        nodes["__void__"] = (w * .90, h * .14, 28)
        box = self._toolbox_rect()
        for i, app in enumerate(stored):
            nodes[app["id"]] = (box.left() + 38 + i * 56, box.center().y() - 6, 15)
        used_slots = 0
        fallback_roots = [app for app in universes if app["id"] not in anchors]

        for app in universes:
            if app["id"] in anchors:
                ax, ay = anchors[app["id"]]
                nodes[app["id"]] = (w * ax, h * ay, self._visual_radius(app))

        # Les univers inconnus se placent sur une grande ellipse, pas sur le paquet central.
        for app in fallback_roots:
            angle = (math.pi * 2 * used_slots / max(1, len(fallback_roots))) - math.pi / 2
            used_slots += 1
            nodes[app["id"]] = (
                w * .5 + math.cos(angle) * w * .34,
                h * .5 + math.sin(angle) * h * .31,
                self._visual_radius(app),
            )

        for app in universes:
            self._apply_manual_position(app, nodes, w, h)

        # Un module peut graviter autour de plusieurs univers : il apparaît
        # une fois par hôte (clé « id » pour l'hôte principal, « id@hôte »
        # pour les suivants). Chaque satellite est une prise indépendante.
        children: Dict[str, List[Tuple[Dict, str]]] = {}
        for app in tools:
            for index, host in enumerate(module_hosts(app)):
                key = app["id"] if (index == 0 and not on_map_free(app)) else f"{app['id']}@{host}"
                children.setdefault(host, []).append((app, key))

        angle_overrides = {
            "existence": {
                "common_services": -2.55,
                "wormhole_access": -0.28,
                "gravity_layer": 0.68,
                "app_manifest": 2.18,
            },
            "common_services": {
                "shared_data_index": -2.25,
                "app_installer": -0.18,
                "app_launcher": 2.28,
            },
            "app_installer": {
                "app_install_verifier": 1.25,
            },
            "gravity_layer": {
                "module_orbit_verifier": 1.62,
            },
            "nebula": {
                "fusion_creator": -0.95,
                "singularity": 1.15,
            },
        }

        placed: set = set()
        visiting: set = set()

        done: set = set()

        def place_children(parent_id: str) -> None:
            if parent_id in visiting or parent_id in done:
                return
            done.add(parent_id)
            parent = nodes.get(parent_id)
            if not parent:
                return
            visiting.add(parent_id)
            child_apps = children.get(parent_id, [])
            count = len(child_apps)
            base_radius = max(110, min(w, h) * (0.13 if count <= 3 else 0.17))
            if parent_id == "existence":
                base_radius = max(235, min(w, h) * 0.30)
            elif parent_id in {"common_services", "gravity_layer"}:
                base_radius = max(145, min(w, h) * 0.18)
            elif parent_id == "app_installer":
                base_radius = max(92, min(w, h) * 0.12)

            for i, (app, key) in enumerate(child_apps):
                if app["id"] in angle_overrides.get(parent_id, {}):
                    angle = angle_overrides[parent_id][app["id"]]
                else:
                    start = -math.pi * 0.82
                    step = (math.pi * 1.64 / max(1, count - 1)) if count > 1 else 0
                    angle = start + i * step
                angle += self.phase
                radius = base_radius + (i // 7) * 58
                orbit_radii[key] = radius
                nodes[key] = (
                    parent[0] + math.cos(angle) * radius,
                    parent[1] + math.sin(angle) * radius * .62,
                    self._visual_radius(app),
                )
                links.append((key, app, parent_id))
                placed.add(key)
                if key == app["id"]:
                    place_children(app["id"])
            visiting.remove(parent_id)

        for parent_id in list(children):
            if parent_id in nodes:
                place_children(parent_id)

        placed_ids = {k.split("@")[0] for k in placed}
        for i, app in enumerate([a for a in tools if a["id"] not in placed_ids]):
            parent = nodes.get(app.get("orbit_of"))
            if not parent:
                continue
            radius = 145
            angle = -math.pi + i * .9 + self.phase
            orbit_radii[app["id"]] = radius
            nodes[app["id"]] = (parent[0] + math.cos(angle) * radius,
                                parent[1] + math.sin(angle) * radius * .62, self._visual_radius(app))
            links.append((app["id"], app, app.get("orbit_of")))

        for key, app, host in links:
            if key in nodes and host in nodes:
                x, y, _ = nodes[key]
                px, py, _ = nodes[host]
                orbit_radii[key] = max(60, math.hypot(x - px, (y - py) / .62))
        self.nodes = nodes
        self.orbit_radii = orbit_radii
        self.links = links

    def _bodies(self):
        """Tous les corps dessinés : (app, clé, hôte ou '')."""
        bodies = []
        linked = {key for key, _, _ in getattr(self, "links", [])}
        for app in self.apps:
            if app["id"] in self.nodes and app["id"] not in linked:
                bodies.append((app, app["id"], ""))
        for key, app, host in getattr(self, "links", []):
            if key in self.nodes:
                bodies.append((app, key, host))
        return bodies

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            self._paint_map(p)
        except Exception as exc:  # noqa: BLE001 — une erreur de dessin ne doit jamais tuer Qt
            print(f"[Existence] erreur de dessin de la carte : {exc!r}", file=sys.stderr)
        finally:
            if p.isActive():
                p.end()

    def _paint_map(self, p):
        if not self.dragging_id:
            self._layout_nodes()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(105, 89, 180, 22), 1))
        for x in range(0, w, 80): p.drawLine(x, 0, x, h)
        for y in range(0, h, 80): p.drawLine(0, y, w, y)
        vx, vy, vr = self.nodes.get("__void__", (w * .90, h * .14, 28))
        p.setBrush(QBrush(QColor("#171329")))
        p.setPen(QPen(QColor("#A78BFA"), 2, Qt.PenStyle.DashLine))
        p.drawEllipse(QRectF(vx-vr, vy-vr, vr*2, vr*2))
        p.setPen(QColor("#C4B5FD")); p.setFont(QFont("", 9, QFont.Weight.DemiBold))
        p.drawText(QRectF(vx-50, vy+vr+6, 100, 20), Qt.AlignmentFlag.AlignHCenter, "VOID")

        # Boîte à outils : les modules y attendent, débranchés mais installés.
        box = self._toolbox_rect()
        hot = bool(self.dragging_id and self._drag_started and box.adjusted(-12, -12, 12, 12).contains(
            QPointF(*self.nodes.get(self.dragging_id, (-1, -1, 0))[:2])))
        p.setBrush(QBrush(QColor(34, 211, 238, 34 if hot else 16)))
        p.setPen(QPen(QColor("#22D3EE" if hot else "#3B5B78"), 2 if hot else 1, Qt.PenStyle.DashLine))
        p.drawRoundedRect(box, 14, 14)
        p.setPen(QColor("#7DD3FC")); p.setFont(QFont("", 9, QFont.Weight.DemiBold))
        p.drawText(QRectF(box.left() + 12, box.top() - 20, 260, 18), Qt.AlignmentFlag.AlignLeft,
                   "🧰  BOÎTE À OUTILS")
        if not any(in_toolbox(a) for a in self.apps):
            p.setPen(QColor(C["text3"])); p.setFont(QFont("", 9))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, "Dépose un module ici pour le débrancher")

        # Tunnels de wormhole : un lien en direct entre deux apps.
        drawn = set()
        for a, b in getattr(self, "wormhole_links", []):
            pair = tuple(sorted((a, b)))
            if pair in drawn or a not in self.nodes or b not in self.nodes:
                continue
            drawn.add(pair)
            ax, ay, _ = self.nodes[a]; bx, by, _ = self.nodes[b]
            mx, my = (ax + bx) / 2, (ay + by) / 2
            dx, dy = bx - ax, by - ay
            ctrl = QPointF(mx - dy * .22, my + dx * .22)
            path = QPainterPath(QPointF(ax, ay)); path.quadTo(ctrl, QPointF(bx, by))
            halo = QColor("#22D3EE"); halo.setAlpha(40)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(halo, 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)); p.drawPath(path)
            pen = QPen(QColor("#67E8F9"), 2, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
            pen.setDashOffset(-self.phase * 40)
            p.setPen(pen); p.drawPath(path)
            p.setPen(QColor("#A5F3FC")); p.setFont(QFont("", 8, QFont.Weight.DemiBold))
            p.drawText(QRectF(ctrl.x() - 40, (my + ctrl.y()) / 2 - 8, 80, 16), Qt.AlignmentFlag.AlignCenter, "⇄ lien")
        for key, app, host in getattr(self, "links", []):
            if key not in self.nodes or host not in self.nodes: continue
            x, y, _ = self.nodes[key]; px, py, _ = self.nodes[host]
            color = QColor(app.get("accent_color", C["cyan"])); color.setAlpha(75)
            p.setPen(QPen(color, 1, Qt.PenStyle.DotLine)); p.drawLine(QPointF(px, py), QPointF(x, y))
        for key, app, host in getattr(self, "links", []):
            if host not in self.nodes: continue
            px, py, _ = self.nodes[host]
            radius = self.orbit_radii.get(key, 145)
            col = QColor(app.get("accent_color", C["cyan"])); col.setAlpha(58)
            p.setPen(QPen(col, 1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(px-radius, py-radius*.62, radius*2, radius*1.24))
        for app, key, host in self._bodies():
            x, y, r = self.nodes[key]; selected = app["id"] == self.hovered
            kind = app.get("app_kind", "")
            is_secondary = kind in {"service", "orbital_module"} or in_toolbox(app)
            color = QColor(app.get("accent_color", C["purple"]))
            glow = QRadialGradient(QPointF(x, y), r * (2.5 if selected else 1.8))
            transparent = QColor(color); transparent.setAlpha(0)
            bright = QColor(color); bright.setAlpha(90 if selected else (30 if is_secondary else 45))
            glow.setColorAt(0, bright); glow.setColorAt(1, transparent)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(glow)); p.drawEllipse(QRectF(x-r*2.5, y-r*2.5, r*5, r*5))
            if (kind == "universe" or (on_map_free(app) and key == app["id"])) and not in_toolbox(app):
                self._draw_universe(p, app, x, y, r, selected, color)
                p.setPen(QColor(C["text"]))
                p.setFont(QFont("", 13 if selected else 12, QFont.Weight.DemiBold))
                label_w = 210
                label = QFontMetrics(p.font()).elidedText(app["name"], Qt.TextElideMode.ElideRight, label_w)
                p.drawText(QRectF(x-label_w/2, y+r+10, label_w, 24), Qt.AlignmentFlag.AlignHCenter, label)
                p.setPen(QColor(C["text3"])); p.setFont(QFont("", 9))
                p.drawText(QRectF(x-110, y+r+31, 220, 20), Qt.AlignmentFlag.AlignHCenter, "UNIVERS")
                continue
            core = QRadialGradient(QPointF(x-r*.25, y-r*.3), r*1.3)
            hi = QColor("#FFFFFF"); hi.setAlpha(220)
            core.setColorAt(0, hi); core.setColorAt(.15, color); core.setColorAt(1, QColor("#171329"))
            pen_color = color.lighter(150)
            if is_secondary and not selected:
                pen_color.setAlpha(150)
            p.setBrush(QBrush(core)); p.setPen(QPen(pen_color, 2 if selected else 1))
            p.drawEllipse(QRectF(x-r, y-r, r*2, r*2))
            if len(module_hosts(app)) > 1:
                # Pastille : ce module est branché sur plusieurs univers.
                p.setBrush(QBrush(QColor("#22D3EE"))); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(x+r*.55, y-r*1.05, 8, 8))
            text_color = QColor(C["text"] if not is_secondary or selected else C["text2"])
            if is_secondary and not selected:
                text_color.setAlpha(210)
            p.setPen(text_color)
            p.setFont(QFont("", 12 if r > 20 else 9, QFont.Weight.DemiBold))
            label_w = 190 if r > 20 else (54 if in_toolbox(app) else 170)
            label = QFontMetrics(p.font()).elidedText(app["name"], Qt.TextElideMode.ElideRight, label_w)
            p.drawText(QRectF(x-label_w/2, y+r+(4 if in_toolbox(app) else 8), label_w, 24),
                       Qt.AlignmentFlag.AlignHCenter, label)
            if r > 20:
                p.setPen(QColor(C["text3"])); p.setFont(QFont("", 9))
                p.drawText(QRectF(x-110, y+r+28, 220, 20), Qt.AlignmentFlag.AlignHCenter, "UNIVERS")
        if getattr(self, "linking", None) and self.linking[1] in self.nodes:
            sx, sy, _ = self.nodes[self.linking[1]]
            pen = QPen(QColor("#67E8F9"), 2, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(sx, sy), self.link_cursor)
            p.setPen(QColor("#A5F3FC")); p.setFont(QFont("", 9, QFont.Weight.DemiBold))
            p.drawText(QRectF(self.link_cursor.x() + 10, self.link_cursor.y() - 18, 220, 18),
                       Qt.AlignmentFlag.AlignLeft, "⇄ relâcher sur une app pour la lier")
        # (le painter est fermé par paintEvent)

    def _body_at(self, pos):
        for app, key, host in reversed(self._bodies()):
            node = self.nodes.get(key)
            if node and math.hypot(pos.x()-node[0], pos.y()-node[1]) <= node[2] + 22:
                return app, key, host
        return None, None, None

    def _app_at(self, pos):
        return self._body_at(pos)[0]

    def mouseMoveEvent(self, event):
        if getattr(self, "linking", None):
            self.link_cursor = event.position()
            self.update()
            return
        if self.dragging_id and self.dragging_id in self.nodes:
            moved = math.hypot(event.position().x() - self.drag_start_pos.x(),
                               event.position().y() - self.drag_start_pos.y())
            if moved < 4:
                return
            pos = event.position() - self.drag_offset
            x = max(28, min(self.width() - 28, pos.x()))
            y = max(28, min(self.height() - 28, pos.y()))
            _, _, r = self.nodes[self.dragging_id]
            self.nodes[self.dragging_id] = (x, y, r)
            self._drag_started = True
            self._suppress_next_double_click = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()
            return

        app = self._app_at(event.position())
        ident = app["id"] if app else None
        if ident != self.hovered:
            self.hovered = ident; self.setCursor(Qt.CursorShape.PointingHandCursor if app else Qt.CursorShape.ArrowCursor); self.update()

    def mousePressEvent(self, event):
        app, key, host = self._body_at(event.position())
        if (app and event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.AltModifier):
            # Alt+glisser : tirer un wormhole d'une app vers une autre.
            self.linking = (app["id"], key)
            self.link_cursor = event.position()
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.update()
            return
        if app and event.button() == Qt.MouseButton.LeftButton:
            self.app_selected.emit(app)
            x, y, _ = self.nodes.get(key, (event.position().x(), event.position().y(), 0))
            self.dragging_id = key
            self._dragging_app = app["id"]
            self._dragging_host = host
            self.drag_offset = event.position() - QPointF(x, y)
            self.drag_start_pos = event.position()
            self._drag_started = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        if getattr(self, "linking", None):
            source_id, _key = self.linking
            self.linking = None
            target, _k, _h = self._body_at(event.position())
            if target is not None and target["id"] != source_id:
                self.wormhole_request.emit(source_id, target["id"])
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
            return
        if self.dragging_id:
            key = self.dragging_id
            app_id = getattr(self, "_dragging_app", key)
            from_host = getattr(self, "_dragging_host", "")
            move = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if self._drag_started and key in self.nodes:
                x, y, _ = self.nodes[key]
                vx, vy, vr = self.nodes.get("__void__", (-9999, -9999, 0))
                app = next((item for item in self.apps if item["id"] == app_id), {})
                if self._toolbox_rect().adjusted(-12, -12, 12, 12).contains(QPointF(x, y)) and can_orbit(app):
                    self.module_plug.emit(app_id, from_host, TOOLBOX_ID, True)
                elif math.hypot(x - vx, y - vy) <= vr + 20:
                    self.app_orbit_changed.emit(app_id, "")
                else:
                    target = None
                    for candidate in reversed(self.apps):
                        if candidate["id"] == app_id:
                            continue
                        node = self.nodes.get(candidate["id"])
                        if node and not in_toolbox(candidate) and math.hypot(x - node[0], y - node[1]) <= node[2] + 28:
                            target = candidate
                            break
                    if target is not None and can_orbit(app):
                        # Déposer sur un autre univers AJOUTE un branchement ;
                        # Maj+déposer le DÉPLACE (quitte l'hôte d'origine).
                        self.module_plug.emit(app_id, from_host, target["id"], move)
                    else:
                        self.app_moved.emit(app_id, x / max(1, self.width()), y / max(1, self.height()))
            self.dragging_id = None
            self._drag_started = False
            self.setCursor(Qt.CursorShape.PointingHandCursor if self.hovered else Qt.CursorShape.ArrowCursor)
            self.update()

    def contextMenuEvent(self, event):
        app, key, host = self._body_at(QPointF(event.pos()))
        if not app or not can_orbit(app):
            return
        menu = QMenu(self)
        hosts = module_hosts(app)
        names = {a["id"]: a.get("name", a["id"]) for a in self.apps}
        for h in hosts:
            action = menu.addAction(f"Débrancher de {names.get(h, h)}")
            action.triggered.connect(lambda _=False, h=h: self.module_plug.emit(app["id"], h, TOOLBOX_ID, True))
        if hosts:
            menu.addSeparator()
            store = menu.addAction("Ranger dans la boîte à outils (tout débrancher)")
            store.triggered.connect(lambda: self.module_plug.emit(app["id"], "", TOOLBOX_ID, True))
        if is_standalone(app):
            if on_map_free(app) and hosts:
                hide = menu.addAction("Retirer l'astre autonome (rester seulement en module)")
                hide.triggered.connect(lambda: self.module_free.emit(app["id"], False))
            elif not on_map_free(app):
                free = menu.addAction("Afficher aussi comme app autonome")
                free.triggered.connect(lambda: self.module_free.emit(app["id"], True))
            menu.addSeparator()
        plug_menu = menu.addMenu("Brancher aussi sur…")
        for candidate in self.apps:
            if ((candidate.get("app_kind") == "universe" or on_map_free(candidate)) and candidate["id"] not in hosts
                    and candidate["id"] != app["id"] and not in_toolbox(candidate)
                    and __import__("modules.compat", fromlist=["is_compatible"]).is_compatible(app, candidate["id"], self.apps)):
                action = plug_menu.addAction(candidate.get("name", candidate["id"]))
                action.triggered.connect(lambda _=False, t=candidate["id"]: self.module_plug.emit(app["id"], "", t, False))
        plug_menu.setEnabled(not plug_menu.isEmpty())
        menu.exec(event.globalPos())

    def mouseDoubleClickEvent(self, event):
        if self._suppress_next_double_click:
            self._suppress_next_double_click = False
            return
        app = self._app_at(event.position())
        if app: self.app_activated.emit(app)


class WindowHost(QFrame):
    """Conteneur de fenêtre native pour les univers externes.

    Sous Wayland, l'hébergement doit être fourni par l'univers lui-même sous
    forme de vue Qt/GTK compatible. Le reparentage d'une fenêtre étrangère est
    conservé uniquement comme compatibilité X11 explicite et optionnelle.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._native_window = None
        self._container = None
        self._embedded_widgets: Dict[str, QWidget] = {}
        self.current_universe_id = ""
        self._pid = None
        self._status = QLabel("Aucun univers embarqué")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        self._status.setStyleSheet(f"color:{C['text2']};font-size:12px;padding:30px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._status)
        self.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border']};border-radius:16px;")

    @property
    def supports_native_reparenting(self) -> bool:
        return (
            os.environ.get("XDG_SESSION_TYPE", "wayland").lower() == "x11"
            and os.environ.get("EXISTENCE_ENABLE_X11_EMBEDDING") == "1"
            and bool(shutil.which("xdotool"))
        )

    def mount_embeddable_view(self, universe_id: str, widget: QWidget) -> None:
        """Monte une vue fournie par l'univers dans le workspace Wayland."""
        if universe_id not in self._embedded_widgets:
            self._embedded_widgets[universe_id] = widget
            widget.setParent(self)
            self.layout().addWidget(widget)
        for current_id, current_widget in self._embedded_widgets.items():
            current_widget.setVisible(current_id == universe_id)
        self._container = self._embedded_widgets[universe_id]
        self.current_universe_id = universe_id
        self._status.hide()
        self._pid = None
        self._status.setAccessibleName(f"Vue embarquée {universe_id}")

    def remove_embeddable_view(self, universe_id: str) -> None:
        widget = self._embedded_widgets.pop(universe_id, None)
        if widget is None:
            return
        if self._container is widget:
            self._container = None
        self.layout().removeWidget(widget)
        widget.close()
        widget.deleteLater()
        if self.current_universe_id == universe_id:
            self.current_universe_id = ""
        if not self._embedded_widgets:
            self._status.show()

    def attach_process(self, pid: int) -> bool:
        if not self.supports_native_reparenting:
            self._status.setText(
                "Wayland : cette application ne fournit pas encore de vue embarquable.\n"
                "La session Existence reste active, mais l'univers conserve sa fenêtre native."
            )
            return False
        try:
            result = subprocess.run(
                [shutil.which("xdotool"), "search", "--pid", str(pid)],
                capture_output=True, text=True, check=False, timeout=2,
            )
            window_ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if not window_ids:
                self._status.setText("Fenêtre en attente…")
                return False
            native_id = int(window_ids[-1])
            native_window = QWindow.fromWinId(native_id)
            if not native_window:
                self._status.setText("La fenêtre native n'est pas intégrable.")
                return False
            self.detach()
            self._native_window = native_window
            self._container = QWidget.createWindowContainer(native_window, self)
            self._container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.layout().addWidget(self._container)
            self._status.hide()
            self._pid = pid
            return True
        except (OSError, ValueError, subprocess.SubprocessError):
            self._status.setText("Impossible de récupérer la fenêtre native.")
            return False

    def detach(self) -> None:
        if self._container is not None:
            self.layout().removeWidget(self._container)
            self._container.deleteLater()
        self._container = None
        self._native_window = None
        self._pid = None
        self._status.show()


class UniverseViewRegistry:
    """Registre de vues fournies par les univers pour Wayland."""

    def __init__(self):
        self._providers: Dict[str, Any] = {}

    def register(self, universe_id: str, provider: Any) -> None:
        if not callable(provider):
            raise TypeError("universe view provider must be callable")
        self._providers[universe_id] = provider

    def has_view(self, universe_id: str) -> bool:
        return universe_id in self._providers

    def create_view(self, universe_id: str, parent: QWidget) -> Optional[QWidget]:
        provider = self._providers.get(universe_id)
        if provider is None:
            return None
        view = provider(parent)
        if not isinstance(view, QWidget):
            raise TypeError(f"{universe_id} provider did not return a QWidget")
        return view


class ProjectManagerDialog(QDialog):
    """Fenêtre de gestion du contexte Project d'Existence."""

    def __init__(self, projects: ProjectManager, parent=None):
        super().__init__(parent)
        self.projects = projects
        self.selected_project_id: Optional[str] = None
        self.standalone_selected = False
        self.setWindowTitle("Projets Existence")
        self.setMinimumSize(520, 420)
        self.setStyleSheet(f"""
            QDialog{{background:{C['bg2']};}}
            QLabel{{color:{C['text2']};}}
            QListWidget{{background:{C['surface']};border:1px solid {C['border']};
                         border-radius:12px;color:{C['text']};padding:6px;}}
            QListWidget::item{{padding:12px;border-radius:8px;}}
            QListWidget::item:selected{{background:{C['purple']};color:white;}}
            QPushButton{{background:{C['surface']};border:1px solid {C['border']};
                         border-radius:16px;color:{C['text']};padding:8px 16px;}}
            QPushButton:hover{{border-color:{C['purple']};}}
        """)
        layout = QVBoxLayout(self)
        title = QLabel("CONTEXTE DE TRAVAIL")
        title.setStyleSheet(f"color:{C['text']};font-size:18px;font-weight:700;")
        layout.addWidget(title)
        self.mode_label = QLabel()
        layout.addWidget(self.mode_label)
        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(lambda item: self._accept_project())
        layout.addWidget(self.project_list, 1)

        buttons = QHBoxLayout()
        new_btn = QPushButton("Nouveau projet")
        new_btn.clicked.connect(self._new_project)
        standalone_btn = QPushButton("Hors projet")
        standalone_btn.clicked.connect(self._select_standalone)
        open_btn = QPushButton("Ouvrir")
        open_btn.clicked.connect(self._accept_project)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        for button in (new_btn, standalone_btn, open_btn, cancel_btn):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self._reload()

    def _reload(self):
        self.project_list.clear()
        current_id = self.projects.data.get("current_project_id")
        for project in self.projects.data["projects"].values():
            item = QListWidgetItem(project.get("name", "Projet sans titre"))
            item.setData(Qt.ItemDataRole.UserRole, project["id"])
            item.setToolTip(
                f"{len(project.get('resources', []))} ressource(s) · "
                f"{len(project.get('universe_resources', {}))} univers"
            )
            self.project_list.addItem(item)
            if project["id"] == current_id and self.projects.in_project:
                self.project_list.setCurrentItem(item)
        self.mode_label.setText(
            f"Mode actuel : {'Projet' if self.projects.in_project else 'Hors projet'}"
        )

    def _new_project(self):
        name, accepted = QInputDialog.getText(self, "Nouveau projet", "Nom du projet :")
        if accepted and name.strip():
            project = self.projects.create(name.strip())
            self.selected_project_id = project["id"]
            self.accept()

    def _select_standalone(self):
        self.standalone_selected = True
        self.accept()

    def _accept_project(self):
        item = self.project_list.currentItem()
        if item is None:
            return
        self.selected_project_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


class ContentArea(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QFrame(); hdr.setFixedHeight(84)
        self.header = hdr
        hdr.setStyleSheet(f"background:{C['bg2']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 0, 24, 0)

        titles = QVBoxLayout(); titles.setSpacing(2)
        self.title_lbl = QLabel("Espace de travail Existence")
        self.title_lbl.setStyleSheet(f"color:{C['text']};font-size:18px;font-weight:700;")
        self.subtitle_lbl = QLabel("Organise les univers, modules orbitaux, services communs et communications.")
        self.subtitle_lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;")
        titles.addWidget(self.title_lbl); titles.addWidget(self.subtitle_lbl); hl.addLayout(titles)
        hl.addStretch()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍  Rechercher…")
        self.search_edit.setFixedSize(220, 36)
        self.search_edit.setStyleSheet(f"""
            QLineEdit{{background:{C['surface']};border:1px solid {C['border']};border-radius:18px;
                       color:{C['text']};padding:0 16px;font-size:12px;}}
            QLineEdit:focus{{border-color:{C['purple']};}}
        """)
        self.workspace_btn = QPushButton("Projet")
        self.workspace_btn.setFixedSize(112, 36)
        self.workspace_btn.setStyleSheet(f"""
            QPushButton{{background:{C['surface']};border:1px solid {C['border']};border-radius:18px;
                         color:{C['text2']};font-size:11px;padding:0 14px;}}
            QPushButton:hover{{border-color:{C['purple']};color:{C['text']};}}
        """)
        self.home_btn = QPushButton("Accueil")
        self.home_btn.setFixedSize(88, 36)
        self.home_btn.setStyleSheet(self.workspace_btn.styleSheet())
        self.switch_universe_btn = QPushButton("Univers")
        self.switch_universe_btn.setFixedSize(92, 36)
        self.switch_universe_btn.setStyleSheet(self.workspace_btn.styleSheet())
        self.close_session_btn = QPushButton("Fermer")
        self.close_session_btn.setFixedSize(88, 36)
        self.close_session_btn.setStyleSheet(f"""
            QPushButton{{background:{C['surface']};border:1px solid {C['red']};border-radius:18px;
                         color:{C['red']};font-size:11px;padding:0 14px;}}
            QPushButton:hover{{background:{C['red']};color:white;}}
        """)
        hl.addWidget(self.home_btn)
        hl.addWidget(self.switch_universe_btn)
        hl.addWidget(self.close_session_btn)
        hl.addWidget(self.workspace_btn)
        hl.addWidget(self.search_edit)
        lay.addWidget(hdr)

        body = QFrame(); body_l = QHBoxLayout(body); body_l.setContentsMargins(22, 12, 22, 22); body_l.setSpacing(16)
        self.orbit_map = OrbitMap(); self.orbit_map.setMinimumWidth(520)
        body_l.addWidget(self.orbit_map, 1)
        self.detail = QLabel("SÉLECTIONNE UN ASTRE\n\nApproche-toi d'un univers, d'un module ou d'un service pour voir sa place dans l'environnement.")
        self.detail.setFixedWidth(210); self.detail.setWordWrap(True); self.detail.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border']};border-radius:16px;padding:18px;color:{C['text2']};font-size:11px;")
        body_l.addWidget(self.detail)

        self.workspace_page = QFrame()
        workspace_l = QVBoxLayout(self.workspace_page)
        workspace_l.setContentsMargins(22, 12, 22, 22)
        workspace_l.setSpacing(10)
        self.workspace_host = WindowHost()
        workspace_l.addWidget(self.workspace_host, 1)
        self.workspace_hint = QLabel(
            "Les univers embarquables apparaissent ici. Sous Wayland, Existence "
            "conserve la session mais laisse la fenêtre autonome."
        )
        self.workspace_hint.setStyleSheet(f"color:{C['text3']};font-size:10px;")
        workspace_l.addWidget(self.workspace_hint)

        self.main_stack = QStackedWidget()
        self.main_stack.addWidget(body)
        self.main_stack.addWidget(self.workspace_page)
        lay.addWidget(self.main_stack)

    def set_compact_mode(self, enabled: bool, universe_name: str = "") -> None:
        """Réduit le chrome Existence sans réduire la vue de l'univers."""
        self.header.setFixedHeight(50 if enabled else 84)
        self.title_lbl.setText(
            f"Existence · {universe_name}" if enabled else "Espace de travail Existence"
        )
        self.workspace_btn.setVisible(not enabled)
        self.search_edit.setVisible(not enabled)
        self.home_btn.setVisible(True)
        self.switch_universe_btn.setVisible(True)
        self.close_session_btn.setVisible(enabled)


# ══════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════

class GalaxyHub(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg       = ConfigManager()
        self.apps      = self.cfg.load()
        self.resources = ResourceRegistry(self.apps)
        self.projects  = ProjectManager()
        self.workspace = WorkspaceSessionManager(self.apps)
        stale_sessions = self.workspace.reconcile_processes(self.apps)
        for stale_id in stale_sessions:
            for app in self.apps:
                if app.get("id") == stale_id:
                    app["lifecycle_state"] = "closed"
                    break
        if stale_sessions:
            self.cfg.save(self.apps)
        self._embedded_views: Dict[str, QWidget] = {}
        # Les communications inter-univers passent par ce routeur unique.
        # Les endpoints sont lancés à la demande, uniquement pour le transport
        # headless, afin de ne jamais créer une seconde fenêtre utilisateur.
        self._ipc_router = ExistenceIPCRouter()
        self._ipc_endpoints: Dict[str, ProcessEndpoint] = {}
        self.modules   = default_registry()
        self._refresh_stardust_bindings()
        self.universe_views = UniverseViewRegistry()
        self._current_universe_id = ""
        try:
            from embedded_views import create_atlas_view, create_cosmos_view, create_nebula_view, create_stardust_view
            self.universe_views.register("atlas", create_atlas_view)
            self.universe_views.register("nebula", create_nebula_view)
            self.universe_views.register("cosmos", create_cosmos_view)
            self.universe_views.register("stardust", lambda parent: create_stardust_view(parent, self.resources, self.modules))
        except (ImportError, OSError):
            pass
        self._cat      = "Toutes"
        self._structure = "Toutes"
        self._query    = ""
        self._cards: Dict[str, AppCard] = {}
        self._processes: Dict[str, subprocess.Popen] = {}
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._refresh)
        self._process_timer = QTimer(self)
        self._process_timer.timeout.connect(self._poll_processes)
        self._process_timer.start(1200)

        self._build_ui()
        self._refresh()
        self._install_wormholes()
        self._install_test_probe()
        # Laisse Qt construire la fenêtre avant de restaurer les univers requis.
        QTimer.singleShot(350, self._restore_workspace)

    def _build_ui(self):
        self.setWindowTitle("Existence — Creative Universe")
        self.setMinimumSize(900, 600)
        self.resize(1180, 740)
        self.setStyleSheet(f"QMainWindow{{background:{C['bg']};}} QWidget{{background:transparent;}}")

        central = QWidget()
        self.setCentralWidget(central)

        # Star field (background layer)
        self.stars = StarField(central)
        self.stars.lower()

        # Overlay panel (sidebar + content) — semi-transparent
        self._overlay = QWidget(central)
        ol = QHBoxLayout(self._overlay)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.category_changed.connect(self._on_cat)
        self.sidebar.structure_changed.connect(self._on_structure)
        self.sidebar.add_app_requested.connect(self._add_app)
        ol.addWidget(self.sidebar)

        self.content = ContentArea()
        self.content.search_edit.textChanged.connect(self._on_search)
        self.content.workspace_btn.clicked.connect(self._choose_project)
        self.content.home_btn.clicked.connect(self._return_to_existence)
        self.content.switch_universe_btn.clicked.connect(self._show_universe_switcher)
        self.content.close_session_btn.clicked.connect(self._close_current_session)
        self.content.orbit_map.app_selected.connect(self._select_app)
        self.content.orbit_map.app_activated.connect(self._launch)
        self.content.orbit_map.app_moved.connect(self._move_app_on_map)
        self.content.orbit_map.app_orbit_changed.connect(self._change_app_orbit)
        self.content.orbit_map.module_plug.connect(self.plug_module)
        self.content.orbit_map.module_free.connect(self.set_module_free)
        self.content.orbit_map.wormhole_request.connect(self.request_wormhole)
        ol.addWidget(self.content)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.stars.setGeometry(0, 0, self.width(), self.height())
        self._overlay.setGeometry(0, 0, self.width(), self.height())
        self._resize_timer.start(120)

    # ── Refresh grid
    def _refresh(self):
        filtered = [a for a in self.apps if self._matches(a)]
        cat_title = "Tout Existence" if self._cat == "Toutes" else self._cat
        self.content.title_lbl.setText(f"{cat_title} · {len(filtered)} astre{'s' if len(filtered) != 1 else ''}")
        active = self.workspace.active_universe_ids()
        project = self.projects.current.get("name") if self.projects.in_project else "hors projet"
        active_text = ", ".join(active) if active else "aucun univers actif"
        self.content.subtitle_lbl.setText(
            f"Projet : {project}  ·  Actifs : {active_text}"
        )
        self.content.workspace_btn.setText(
            "Projet" if self.projects.in_project else "Hors projet"
        )
        self.content.orbit_map.set_apps(filtered)

    def _select_app(self, app_data: dict):
        kind = app_data.get("app_kind") or ("orbital_module" if app_data.get("orbit_of") else "universe")
        orbit = APP_KIND_LABELS.get(kind, "ASTRE")
        status, status_msg = verify_app_readiness(app_data)
        capabilities = app_data.get("capabilities", [])
        cap_text = ", ".join(capabilities[:4]) if capabilities else "à définir"
        parent = app_data.get("orbit_of", "")
        orbit_relation = app_data.get("orbit_relation", "")
        parent_text = f"\nORBITE\n{parent} · {orbit_relation or 'relation à définir'}\n\n" if parent else ""
        lifecycle = app_data.get("lifecycle_state", default_lifecycle_state(app_data))
        session = self.workspace.session(app_data.get("id", ""))
        namespace = app_data.get("resource_namespace", "resource://...")
        resource_count = sum(1 for uri, res in self.resources.resources.items()
                             if uri.startswith(namespace) and res.get("lifecycle") != "deleted")
        if app_data.get("system_role"):
            launch = "Double-clique pour activer ce module système."
        elif lifecycle == "active":
            launch = "Univers actif dans l'environnement."
        elif status == AppReadiness.READY:
            launch = "Double-clique pour ouvrir."
        elif status == AppReadiness.INSTALLABLE:
            launch = "Double-clique pour lancer l'installation préparée."
        else:
            launch = "Configure son exécutable ou son script d'installation lorsque tu seras prêt."
        self.content.detail.setText(
            f"{orbit}\n\n{app_data['name'].upper()}\n\n{display_version(app_data)}\n\n"
            f"{app_data.get('description', '')}\n\n{parent_text}CYCLE\n{lifecycle}\n\n"
            f"RESSOURCES\n{namespace}\n{resource_count} ressource(s)\n\n"
            f"CAPACITÉS\n{cap_text}\n\nSTATUT\n{status_msg}\n\n{launch}")
        if session:
            state = session.get("state", "closed")
            resources = len(session.get("resources", []))
            self.content.detail.setText(
                self.content.detail.text() +
                f"\n\nSESSION WORKSPACE\n{state} · {resources} ressource(s) associée(s)"
            )
        embedding = app_data.get("embedding_mode", "external")
        surface_text = (
            "vue fournie par l'univers (compatible Wayland)"
            if embedding == "embeddable_view" else
            "fenêtre autonome médiée par Existence"
        )
        self.content.detail.setText(
            self.content.detail.text() + f"\n\nSURFACE\n{surface_text}"
        )

    def _add_placeholder(self) -> QFrame:
        f = QFrame()
        f.setFixedSize(AppCard.CARD_W, AppCard.CARD_H)
        f.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        f.setStyleSheet(f"""
            QFrame{{background:{C['surface']};border:2px dashed {C['border']};border-radius:16px;}}
            QFrame:hover{{border-color:{C['purple']};background:#0f0b28;}}
        """)
        inner = QVBoxLayout(f)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus = QLabel("+")
        plus.setStyleSheet(f"color:{C['text3']};font-size:30px;background:transparent;")
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(plus)
        txt = QLabel("Nouvelle application")
        txt.setStyleSheet(f"color:{C['text3']};font-size:12px;background:transparent;")
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(txt)
        f.mousePressEvent = lambda _: self._add_app()
        return f

    def _matches(self, app: dict) -> bool:
        if app.get("ecosystem_id", ECOSYSTEM_ID) != ECOSYSTEM_ID:
            return False
        if not self._matches_structure(app):
            return False
        if self._cat != "Toutes" and app.get("category") != self._cat:
            return False
        if self._query:
            q = self._query.lower()
            return (q in app["name"].lower()
                    or q in app.get("description", "").lower()
                    or any(q in t for t in app.get("tags", [])))
        return True

    def _matches_structure(self, app: dict) -> bool:
        if self._structure == "Toutes":
            return True
        kind = app.get("app_kind", "")
        role = app.get("system_role", "")
        if self._structure == "Univers":
            return kind == "universe"
        if self._structure == "Modules":
            return is_orbital_module(app)
        if self._structure == "Services":
            return kind == "service" and role not in {"core", "gravity", "wormholes", "resource_index", "common_services"}
        if self._structure == "Infrastructure":
            return kind == "environment" or role in {"core", "gravity", "wormholes", "resource_index", "common_services"}
        return True

    # ── Handlers
    def _on_cat(self, cat: str):
        self._cat = cat; self._refresh()

    def _on_structure(self, item: str):
        self._structure = item; self._refresh()

    def _move_app_on_map(self, app_id: str, x: float, y: float):
        for app in self.apps:
            if app.get("id") == app_id:
                if is_standalone(app) and not in_toolbox(app):
                    # Module hybride lâché dans le vide : il devient aussi un
                    # astre autonome, sans quitter ses univers hôtes.
                    app["map_free"] = True
                    app["map_position"] = {"x": round(max(0.02, min(0.98, x)), 4),
                                           "y": round(max(0.02, min(0.98, y)), 4)}
                    break
                if app.get("orbit_of"):
                    # Le drag hors d'une cible change seulement la position du
                    # curseur, pas l'orbite : le module reprend sa trajectoire.
                    app["map_position"] = {}
                    self._refresh()
                    return
                app["map_position"] = {"x": round(max(0.02, min(0.98, x)), 4),
                                       "y": round(max(0.02, min(0.98, y)), 4)}
                break
        self.cfg.save(self.apps)
        self._refresh()

    def stardust_plugged_creators(self) -> dict:
        """État réel de chaque module Creator en orbite de StarDust."""
        plugged = {}
        for module_id in STARDUST_CREATOR_MODULES:
            app = next((item for item in self.apps if item.get("id") == module_id), None)
            plugged[module_id] = bool(
                app
                and "stardust" in module_hosts(app)
                and app.get("app_kind") == "orbital_module"
                and app.get("installed", False)
                and app.get("lifecycle_state", "available") != "closed"
            )
        return plugged

    def _refresh_stardust_bindings(self):
        """Reflète dans le registre les modules Creator réellement branchés sur StarDust."""
        plugged = self.stardust_plugged_creators()
        changed = False
        for module_id, kinds in STARDUST_CREATOR_MODULES.items():
            for kind in kinds:
                self.modules.unbind_resource(kind, "stardust")
                if plugged[module_id]:
                    self.modules.bind_resource(kind, "stardust", "read_write")
            app = next((item for item in self.apps if item.get("id") == module_id), None)
            if app is not None:
                activation = "active" if plugged[module_id] else "inactive"
                if app.get("activation_state") != activation:
                    app["activation_state"] = activation
                    app["availability_state"] = "available"
                    changed = True
        if changed:
            self.cfg.save(self.apps)
        view = self._embedded_views.get("stardust")
        if view is None:
            return
        if hasattr(view, "refresh_existence_creators"):
            view.refresh_existence_creators(plugged)
        elif hasattr(view, "refresh_creator_connection"):   # anciens builds StarDust
            view.refresh_creator_connection(plugged["fusion_creator"])

    def plug_module(self, app_id: str, from_host: str, target: str, move: bool = False):
        """Branchements multiples et boîte à outils.

        • cible = univers : ajoute ce branchement (ou déplace depuis ``from_host``
          si ``move``) ; un module de la boîte à outils en ressort.
        • cible = boîte à outils : débranche de ``from_host`` (ou de tout si
          vide) ; sans plus aucun hôte, le module est rangé dans la boîte."""
        app = next((item for item in self.apps if item.get("id") == app_id), None)
        if app is None or not can_orbit(app):
            return
        if app.get("app_kind") == "service" or default_kind(app_id) == "service":
            # Un service commun n'a qu'une orbite : comportement historique.
            if target != TOOLBOX_ID:
                self._change_app_orbit(app_id, target)
            return
        hosts = module_hosts(app)
        if target == TOOLBOX_ID:
            hosts = [h for h in hosts if from_host and h != from_host]
        else:
            if target == app_id:
                return
            node = next((item for item in self.apps if item.get("id") == target), None)
            if node is None:
                return
            from modules.compat import compatible_hosts, is_compatible
            if not is_compatible(app, target, self.apps):
                allowed = ", ".join(next((a.get("name", h) for a in self.apps if a.get("id") == h), h)
                                    for h in (compatible_hosts(app, self.apps) or []))
                self._notify(f"{app.get('name', app_id)} ne peut pas se brancher sur {node.get('name', target)}"
                             + (f" — compatible avec : {allowed}" if allowed else ""))
                return
            # Pas de cycle : la cible ne doit pas graviter (même indirectement) autour du module.
            seen, cursor = set(), node
            while cursor is not None and cursor.get("id") not in seen:
                if cursor.get("id") == app_id:
                    return
                seen.add(cursor.get("id"))
                cursor = next((i for i in self.apps if i.get("id") == cursor.get("orbit_of")), None)
            if move and from_host:
                hosts = [h for h in hosts if h != from_host]
            if target not in hosts:
                hosts.append(target)
        set_module_hosts(app, hosts)
        app["app_kind"] = "orbital_module"
        if target == TOOLBOX_ID and not from_host:
            app["map_free"] = False  # « ranger » = tout débrancher, astre libre compris
        if hosts:
            app["orbit_relation"] = "available_from"
        elif is_standalone(app) and app.get("map_free"):
            app["orbit_relation"] = "standalone"
        else:
            app["orbit_relation"] = "toolbox"
        app["lifecycle_state"] = "available"
        app["installed"] = True
        app["map_position"] = {}
        self._after_orbit_change()

    def _install_test_probe(self):
        if not os.environ.get("EXISTENCE_TEST_PROBE"):
            return
        from modules.test_probe import install_probe
        self._test_probe = install_probe(self, "existence", state=lambda: {
            "hosts": {a["id"]: module_hosts(a) for a in self.apps if is_module(a)},
            "running": [k for k, p in self._processes.items() if p.poll() is None],
            "last_notice": getattr(self, "_last_notice", ""),
            "wormhole_links": [l.get("apps") for l in (self.wormhole.links("*") if getattr(self, "wormhole", None) else [])],
        }, commands={
            "plug": lambda module, source, target, move=False: self.plug_module(module, source, target, bool(move)),
            "request_wormhole": self.request_wormhole,
            "launch": lambda app_id: self._launch(next(a for a in self.apps if a["id"] == app_id)),
        })

    def _notify(self, text: str) -> None:
        self._last_notice = text
        try:
            self.statusBar().showMessage(text, 6000)
        except RuntimeError:
            pass
        if not os.environ.get("EXISTENCE_TEST_PROBE"):
            QMessageBox.information(self, "Existence", text)

    def request_wormhole(self, source: str, target: str):
        """Alt+glisser sur la carte : demande à la source de lier son contenu actif à la cible."""
        from modules.wormhole import WORMHOLE_APPS
        names = {a.get("id"): a.get("name", a.get("id")) for a in self.apps}
        live = {k for k, v in WORMHOLE_APPS.items() if v.get("live")}
        if source not in live or target not in WORMHOLE_APPS:
            self._notify("Lien en direct possible entre : " + ", ".join(names.get(k, k) for k in sorted(live))
                         + (" (et envoi vers Singularity)" if "singularity" in WORMHOLE_APPS else ""))
            return
        if target not in live:
            self._notify(f"{names.get(target, target)} ne sait que recevoir : utilise « Envoyer vers » depuis "
                         f"{names.get(source, source)}.")
            return
        hole = getattr(self, "wormhole", None)
        if hole is None:
            return
        hole.control(source, "link_active", to=target)
        self.statusBar().showMessage(
            f"⇄ Demande envoyée : {names.get(source, source)} va lier son contenu actif avec "
            f"{names.get(target, target)} (l'app s'ouvre si besoin)", 6000)

    def set_module_free(self, app_id: str, free: bool):
        app = next((item for item in self.apps if item.get("id") == app_id), None)
        if app is None or not is_standalone(app):
            return
        app["map_free"] = bool(free)
        if free and app.get("orbit_relation") == "toolbox":
            app["orbit_relation"] = "standalone"
        app["installed"] = True
        self._after_orbit_change()

    def _after_orbit_change(self):
        self.cfg.save(self.apps)
        for view in self._embedded_views.values():
            if hasattr(view, "refresh_existence_modules"):
                view.refresh_existence_modules()
        self._refresh_stardust_bindings()
        self._refresh()
        center = getattr(self, "_existence_center", None)
        if center is not None and hasattr(center, "refresh_modules"):
            center.refresh_modules()

    def _change_app_orbit(self, app_id: str, orbit_of: str):
        """Branche un module sur un astre, ou le débranche via Void."""
        moved = next((item for item in self.apps if item.get("id") == app_id), None)
        target = next((item for item in self.apps if item.get("id") == orbit_of), None)
        if moved is None:
            return
        if orbit_of and (not can_orbit(moved) or target is None):
            return

        # Reject any target in the moved node's descendant chain.
        # This keeps the orbit graph acyclic even for programmatic updates.
        seen = set()
        cursor = target
        while cursor is not None and cursor.get("id") not in seen:
            if cursor.get("id") == app_id:
                return
            seen.add(cursor.get("id"))
            parent_id = cursor.get("orbit_of")
            cursor = next((item for item in self.apps if item.get("id") == parent_id), None)

        changed = None
        for app in self.apps:
            if app.get("id") == app_id:
                if orbit_of == app_id:
                    return
                set_module_hosts(app, [orbit_of] if orbit_of else [])
                if not orbit_of and is_standalone(app):
                    app["map_free"] = True
                # Un service reste un service (et donc ré-attachable) ; un module
                # détaché devient un univers autonome, comme avant.
                is_service = app.get("app_kind") == "service" or default_kind(app_id) == "service"
                if is_service:
                    app["app_kind"] = "service"
                    app["orbit_relation"] = ("shared_service" if orbit_of else "detached")
                else:
                    app["app_kind"] = "orbital_module" if orbit_of else "universe"
                    app["orbit_relation"] = "available_from" if orbit_of else "detached"
                app["map_position"] = {}
                changed = app
                break
        if changed is None:
            return
        self.cfg.save(self.apps)
        # Toutes les vues embarquées relisent l'état : le module devient
        # immédiatement visible dans son nouvel univers parent.
        for view in self._embedded_views.values():
            if hasattr(view, "refresh_existence_modules"):
                view.refresh_existence_modules()
        self._refresh_stardust_bindings()
        self._refresh()

    def _on_search(self, q: str):
        self._query = q; self._refresh()

    def _choose_project(self):
        dialog = ProjectManagerDialog(self.projects, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.standalone_selected:
            self._leave_project_mode()
            return
        if dialog.selected_project_id:
            selected = self.projects.select(dialog.selected_project_id)
            self.workspace.set_project(selected["name"])
            self._refresh()

    def _leave_project_mode(self):
        for universe_id in list(self._embedded_views):
            self._close_session(universe_id)
        self.projects.leave_project()
        self._return_to_existence()

    def _show_universe_view(self, app_data: dict) -> None:
        """Change de vue sans arrêter les processus vivants."""
        universe_id = app_data.get("id", "")
        self._current_universe_id = universe_id
        self.content.workspace_host.current_universe_id = universe_id
        self.content.main_stack.setCurrentIndex(1)
        self.content.set_compact_mode(True, app_data.get("name", universe_id))
        self.sidebar.setVisible(False)
        can_embed = (
            self.projects.in_project
            and app_data.get("embedding_mode") == "embeddable_view"
            and self.universe_views.has_view(universe_id)
        )
        if can_embed and universe_id in self._embedded_views:
            self.content.workspace_host.mount_embeddable_view(
                universe_id, self._embedded_views[universe_id]
            )
            self.content.workspace_hint.setText(
                f"Vue embarquée · {app_data.get('name', universe_id)} · "
                "session conservée par Existence."
            )
            return
        if can_embed:
            view = self.universe_views.create_view(universe_id, self.content.workspace_host)
            if view is not None:
                self.content.workspace_host.mount_embeddable_view(universe_id, view)
                self.content.workspace_hint.setText(
                    f"Vue embarquée · {app_data.get('name', universe_id)} · "
                    "processus et session conservés par Existence."
                )
                return
        self.content.workspace_host._status.setText(
            f"{app_data.get('name', universe_id)} est actif dans la Workplace, "
            "mais ne fournit pas encore de vue Wayland embarquable.\n"
            "Le processus reste vivant et l'IPC Existence reste disponible."
        )
        self.content.workspace_hint.setText(
            "Application externe · Existence conserve la session et l'IPC sans créer de vue embarquée."
        )

    def _return_to_existence(self) -> None:
        """Retourne à la carte Existence sans arrêter les univers actifs."""
        self.content.main_stack.setCurrentIndex(0)
        self.content.set_compact_mode(False)
        self.sidebar.setVisible(True)
        self._current_universe_id = ""
        self._refresh()

    def _show_universe_switcher(self) -> None:
        menu = QMenu(self)
        universes = [app for app in self.apps if app.get("app_kind") == "universe"]
        for app_data in universes:
            action = QAction(app_data.get("name", app_data["id"]), menu)
            active = app_data["id"] in self.workspace.active_universe_ids() or app_data["id"] in self._embedded_views
            action.setText(f"● {app_data.get('name', app_data['id'])}" if active else app_data.get("name", app_data["id"]))
            action.triggered.connect(lambda checked=False, item=app_data: self._launch(item))
            menu.addAction(action)
        menu.addSeparator()
        active_ids = self.workspace.active_universe_ids()
        for active_id in active_ids:
            active_app = next((item for item in universes if item.get("id") == active_id), None)
            if active_app:
                close_action = menu.addAction(f"Fermer {active_app.get('name', active_id)}")
                close_action.triggered.connect(
                    lambda checked=False, item_id=active_id: self._close_session(item_id)
                )
        if active_ids:
            menu.addSeparator()
        home = menu.addAction("Retour à l'accueil Existence")
        home.triggered.connect(self._return_to_existence)
        menu.exec(self.content.switch_universe_btn.mapToGlobal(
            self.content.switch_universe_btn.rect().bottomLeft()
        ))

    def _close_current_session(self) -> None:
        if self._current_universe_id:
            self._close_session(self._current_universe_id)

    def _close_session(self, universe_id: str) -> None:
        """Ferme uniquement la session d'un univers, jamais Existence."""
        view = self._embedded_views.pop(universe_id, None)
        if view is not None:
            self.content.workspace_host.remove_embeddable_view(universe_id)
        process = self._processes.pop(universe_id, None)
        if process is not None:
            try:
                if hasattr(process, "terminate"):
                    process.terminate()
                else:
                    os.kill(process.pid, 15)
            except OSError:
                pass
        self.workspace.mark_closed(universe_id)
        self._set_lifecycle(universe_id, "closed")
        append_event("universe.session_closed", {
            "app_id": universe_id,
            "workspace": self.workspace.data["current_workspace"],
        })
        if self._current_universe_id == universe_id:
            self._return_to_existence()

    def _open_embedded_universe(self, app_data: dict) -> None:
        universe_id = app_data["id"]
        self._retire_legacy_external_process(app_data)
        existing = self._embedded_views.get(universe_id)
        if existing is not None:
            if universe_id != "stardust":
                self._show_universe_view(app_data)
                existing.show()
                existing.raise_()
                return
            # Double-cliquer StarDust recharge toujours le fichier courant,
            # même si Existence est resté ouvert depuis un ancien build.
            self.content.workspace_host.remove_embeddable_view(universe_id)
            existing.deleteLater()
            self._embedded_views.pop(universe_id, None)
        try:
            view = self.universe_views.create_view(universe_id, self.content.workspace_host)
            if view is None:
                return
            self._embedded_views[universe_id] = view
            session = self.workspace.register_started(universe_id, os.getpid())
            session["mode"] = "embedded_view"
            session["window"]["state"] = "embedded"
            self.workspace.save()
            self._set_lifecycle(universe_id, "active")
            self._show_universe_view(app_data)
            view.show()
        except Exception as exc:
            append_event("universe.embedded_failed", {
                "app_id": universe_id,
                "error": str(exc),
            })
            QMessageBox.warning(self, "Vue embarquée indisponible", str(exc))

    def _retire_legacy_external_process(self, app_data: dict) -> None:
        """Ferme uniquement l'ancien processus de cette app, jamais un PID arbitraire."""
        session = self.workspace.session(app_data.get("id", ""))
        if not session or session.get("mode", "external") != "external":
            return
        pid = int(session.get("pid", 0) or 0)
        if pid <= 0 or pid == os.getpid():
            return
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="ignore")
            expected = Path(app_data.get("exec_path", "")).name
            if expected and expected in cmdline:
                os.kill(pid, 15)
                self._processes.pop(app_data.get("id", ""), None)
                session["state"] = "closed"
                session["desired"] = False
                self.workspace.save()
                append_event("universe.legacy_external_closed", {
                    "app_id": app_data.get("id", ""), "pid": pid,
                })
        except (OSError, ValueError):
            pass

    def _add_app(self):
        dlg = AppDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.apps.append(dlg.result_data)
            self.cfg.save(self.apps)
            self._refresh()

    def _edit_app(self, app_data: dict):
        dlg = AppDialog(app_data=app_data, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            upd = dlg.result_data
            for i, a in enumerate(self.apps):
                if a["id"] == upd["id"]:
                    self.apps[i] = upd; break
            self.cfg.save(self.apps)
            self._refresh()

    def _remove(self, app_id: str):
        app = next((a for a in self.apps if a["id"] == app_id), None)
        if not app: return
        reply = QMessageBox.question(
            self, "Supprimer ?",
            f"Retirer « {app['name']} » d'Existence ?\n"
            "(L'app ne sera pas désinstallée du système.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.apps = [a for a in self.apps if a["id"] != app_id]
            self.cfg.save(self.apps)
            self._refresh()

    def _restore_workspace(self):
        """Restaure uniquement les univers marqués nécessaires par le workspace."""
        required = self.workspace.required_universe_ids(self.apps, self.resources.resources)
        for app_id in required:
            app_data = next((app for app in self.apps if app.get("id") == app_id), None)
            if not app_data:
                continue
            persisted = self.workspace.session(app_id)
            if (persisted and persisted.get("mode") == "embedded_view"
                    and not self.projects.in_project):
                # Une vue embarquée appartient au contexte projet ; hors projet,
                # elle ne doit jamais être relancée automatiquement ni devenir
                # une seconde application externe.
                self.workspace.mark_closed(app_id)
                self._set_lifecycle(app_id, "closed")
                continue
            status, reason = verify_app_readiness(app_data)
            if status == AppReadiness.READY:
                self._launch(app_data, restoring=True)
            else:
                append_event("workspace.restore_skipped", {
                    "app_id": app_id,
                    "reason": reason,
                    "workspace": self.workspace.data["current_workspace"],
                })

    def _launch(self, app_data: dict, restoring: bool = False):
        if app_data.get("id") == "resource_center" and not restoring:
            self.open_existence_center("resources")
            return
        role = app_data.get("system_role", "")
        if role:
            self._run_system_module(role)
            return
        if is_module(app_data) and not app_data.get("exec_path"):
            self._activate_module(app_data)
            return

        if (self.projects.in_project
                and app_data.get("embedding_mode") == "embeddable_view"
                and self.universe_views.has_view(app_data["id"])):
            self._open_embedded_universe(app_data)
            return

        # Un clic sur un univers déjà ouvert active sa session existante.
        # Le hub ne crée jamais un second processus pour le même univers.
        existing = self._processes.get(app_data["id"])
        if existing is None:
            persisted = self.workspace.session(app_data["id"])
            persisted_pid = int(persisted.get("pid", 0)) if persisted else 0
            if (persisted and persisted.get("mode", "external") == "external"
                    and persisted.get("state") == "active"
                    and persisted_pid > 0 and persisted_pid != os.getpid()):
                restored = ExistingProcessHandle(persisted_pid)
                if restored.poll() is None:
                    self._processes[app_data["id"]] = restored
                    existing = restored
                    append_event("universe.reconnected", {
                        "app_id": app_data["id"], "pid": persisted_pid,
                        "workspace": self.workspace.data["current_workspace"],
                    })
        if existing is not None and existing.poll() is None:
            self.workspace.register_started(app_data["id"], existing.pid)
            self._activate_process_window(existing.pid)
            self._show_universe_view(app_data)
            self._try_attach_window(app_data["id"], existing.pid)
            append_event("universe.activated", {
                "app_id": app_data["id"], "pid": existing.pid,
                "workspace": self.workspace.data["current_workspace"],
            })
            self._select_app(app_data)
            return

        status, status_msg = verify_app_readiness(app_data)
        if status == AppReadiness.INSTALLABLE:
            if not restoring:
                self._install_app(app_data)
            return
        if status == AppReadiness.BROKEN_EXEC:
            if not restoring:
                QMessageBox.warning(self, "App non prête", status_msg)
            return

        ep = app_data.get("exec_path", "")
        if not ep:
            if not restoring:
                QMessageBox.information(
                    self, "Aucun exécutable",
                    f"Aucun exécutable configuré pour « {app_data['name']} ».\n"
                    "Clique sur ⚙ Configurer pour en ajouter un.",
                )
            return
        try:
            args = [ep] + app_data.get("exec_args", [])
            cwd = app_data.get("working_dir", "").strip() or None
            proc = subprocess.Popen(args, cwd=cwd, start_new_session=True)
            self._processes[app_data["id"]] = proc
            self.workspace.register_started(app_data["id"], proc.pid)
            self._show_universe_view(app_data)
            QTimer.singleShot(800, lambda: self._try_attach_window(app_data["id"], proc.pid))
            self._set_lifecycle(app_data["id"], "active")
            append_event("universe.started", {
                "app_id": app_data["id"],
                "name": app_data.get("name", app_data["id"]),
                "pid": proc.pid,
                "workspace": self.workspace.data["current_workspace"],
            })
        except Exception as exc:
            self._set_lifecycle(app_data["id"], "error")
            append_event("universe.failed", {
                "app_id": app_data["id"],
                "name": app_data.get("name", app_data["id"]),
                "error": str(exc),
            })
            QMessageBox.critical(self, "Erreur de lancement", str(exc))

    def _activate_module(self, app_data: dict) -> None:
        """Active une capacité dans son hôte sans créer de processus."""
        app_data["availability_state"] = "available"
        app_data["activation_state"] = "active"
        app_data["lifecycle_state"] = "active"
        self.cfg.save(self.apps)
        if app_data.get("id") in STARDUST_CREATOR_MODULES:
            self._refresh_stardust_bindings()
        append_event("module.activated", {
            "module_id": app_data.get("id"),
            "host": app_data.get("orbit_of") or ECOSYSTEM_ID,
        })
        self._refresh()

    @staticmethod
    def _activate_process_window(pid: int) -> bool:
        """Active la fenêtre du processus quand le gestionnaire de fenêtres le permet."""
        xdotool = shutil.which("xdotool")
        if not xdotool:
            return False
        try:
            result = subprocess.run(
                [xdotool, "search", "--pid", str(pid), "windowactivate"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=2,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def _try_attach_window(self, app_id: str, pid: int, attempt: int = 0) -> None:
        if self._processes.get(app_id) is None or self._processes[app_id].poll() is not None:
            return
        if self.content.workspace_host.attach_process(pid):
            self.workspace.current["ui"]["windows"].setdefault(app_id, {})["embedded"] = True
            self.workspace.save()
            return
        # Les fenêtres GTK peuvent apparaître après le processus. On réessaie
        # brièvement sans bloquer la boucle Qt.
        if attempt < 8 and self.content.workspace_host.supports_native_reparenting:
            QTimer.singleShot(500, lambda: self._try_attach_window(app_id, pid, attempt + 1))

    def _set_lifecycle(self, app_id: str, state: str):
        for app in self.apps:
            if app.get("id") == app_id:
                app["lifecycle_state"] = state
                if is_universe(app):
                    app["process_state"] = {
                        "active": "running",
                        "closed": "stopped",
                        "error": "crashed",
                    }.get(state, app.get("process_state", "stopped"))
                    app["session_state"] = "active" if state == "active" else "closed"
                    app["view_state"] = "embedded" if app_id in self._embedded_views else "external"
                break
        self.cfg.save(self.apps)
        self._refresh()

    def _poll_processes(self):
        closed = []
        for app_id, proc in self._processes.items():
            code = proc.poll()
            if code is None:
                continue
            closed.append((app_id, code))
        for app_id, code in closed:
            self._processes.pop(app_id, None)
            self.workspace.mark_closed(app_id)
            self._set_lifecycle(app_id, "closed")
            append_event("universe.closed", {"app_id": app_id, "returncode": code})

    def _install_app(self, app_data: dict):
        script = app_data.get("install_script", "").strip()
        if not script:
            QMessageBox.information(
                self, "Installation à préparer",
                "Cette app a une source connue, mais aucun script d'installation local n'est encore configuré.",
            )
            return

        reply = QMessageBox.question(
            self, "Lancer l'installation ?",
            f"Exécuter le script d'installation pour « {app_data['name']} » ?\n\n{script}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            subprocess.Popen([str(Path(script).expanduser())], start_new_session=True)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'installation", str(exc))

    def _ipc_command(self, universe_id: str) -> Optional[List[str]]:
        """Retourne le bridge headless d'un univers, sans lancer sa GUI."""
        if universe_id == "nebula":
            adapter = _app_dir("nebula") / "EXISTENCE" / "adapter.py"
            return [sys.executable, str(adapter), "--message"] if adapter.exists() else None
        if universe_id == "atlas":
            adapter = Path(_native("atlas", "AtlasExistenceAdapter", "build_atlas"))
            return [str(adapter), "--stdio"] if adapter.exists() else None
        if universe_id == "singularity":
            adapter = _app_dir("singularity") / "existence_adapter.py"
            return [sys.executable, str(adapter)] if adapter.exists() else None
        return None

    def _ipc_endpoint(self, universe_id: str) -> ProcessEndpoint:
        endpoint = self._ipc_endpoints.get(universe_id)
        if endpoint is not None and endpoint.process.poll() is None:
            return endpoint
        command = self._ipc_command(universe_id)
        if not command:
            raise RuntimeError(f"aucun bridge IPC headless n'est installé pour {universe_id}")
        endpoint = ProcessEndpoint(command)
        self._ipc_endpoints[universe_id] = endpoint
        self._ipc_router.register(universe_id, endpoint)
        endpoint.request("handshake")
        return endpoint

    def _route_real_message(self, event: dict) -> dict:
        """Livre réellement un message après validation du contrat catalogue."""
        target = event["target"]
        self._ipc_endpoint(target)
        payload = dict(event.get("payload") or {})
        return self._ipc_router.route(
            event["source"], target, event["target_message"],
            resource=event.get("resource", ""), **payload,
        )

    def closeEvent(self, event):
        for endpoint in list(self._ipc_endpoints.values()):
            endpoint.close()
        self._ipc_endpoints.clear()
        super().closeEvent(event)

    # ── Wormholes : Existence ouvre l'app qui a du courrier et trace les tunnels ──
    def _install_wormholes(self):
        try:
            from modules.wormhole import Wormhole, WORMHOLE_APPS
            self.wormhole = Wormhole(ECOSYSTEM_ID)
            self._wormhole_apps = WORMHOLE_APPS
        except (ImportError, OSError):
            self.wormhole = None
            return
        self._wormhole_launch_times: Dict[str, float] = {}
        self._wormhole_timer = QTimer(self)
        self._wormhole_timer.timeout.connect(self._wormhole_tick)
        self._wormhole_timer.start(1500)
        QTimer.singleShot(2000, lambda: self.wormhole.cleanup())

    def _wormhole_tick(self):
        hole = getattr(self, "wormhole", None)
        if hole is None:
            return
        now = time.time()
        for app_id in self._wormhole_apps:
            if not hole.pending(app_id) or hole.is_alive(app_id):
                continue
            if now - self._wormhole_launch_times.get(app_id, 0) < 30:
                continue  # l'app démarre encore
            app = next((a for a in self.apps if a.get("id") == app_id), None)
            if not app or not app.get("installed", True) or not app.get("exec_path"):
                continue
            self._wormhole_launch_times[app_id] = now
            append_event("wormhole.launch_target", {"app_id": app_id, "pending": hole.pending(app_id)})
            try:
                self._launch(app)
            except Exception as exc:  # noqa: BLE001
                append_event("wormhole.launch_failed", {"app_id": app_id, "error": str(exc)})
        try:
            pairs = [tuple(link.get("apps", [])[:2]) for link in hole.links("*")]
        except OSError:
            pairs = []
        self.content.orbit_map.wormhole_links = [p for p in pairs if len(p) == 2]

    def open_existence_center(self, tab: str = "catalog"):
        """Catalogue d'apps / modules et vue des Ressources (double-clic sur Existence)."""
        from app_catalog import ExistenceCenter
        center = getattr(self, "_existence_center", None)
        if center is None:
            center = ExistenceCenter(self, tab)
            center.finished.connect(lambda *_: setattr(self, "_existence_center", None))
            self._existence_center = center
        else:
            center.show_tab(tab)
        center.show()
        center.raise_()
        center.activateWindow()

    def _run_system_module(self, role: str):
        if role in {"core", "installer"}:
            self.open_existence_center("catalog")
            return

        if role == "install_verifier":
            report = []
            for app in self.apps:
                if app.get("system_role"):
                    continue
                installed = "installée" if is_app_installed(app) else "non installée"
                report.append(f"• {app['name']} — {installed}")
            QMessageBox.information(
                self, "Sous-couche de l'installateur",
                "\n".join(report) if report else "Aucune app personnelle à vérifier.",
            )
            return

        if role == "launcher":
            ready = [app["name"] for app in self.apps
                     if not app.get("system_role") and verify_app_readiness(app)[0] == AppReadiness.READY]
            QMessageBox.information(
                self, "Launcher D'app",
                "Apps prêtes à lancer :\n" + ("\n".join(f"• {name}" for name in ready) if ready else "Aucune pour le moment."),
            )
            return

        if role == "module_verifier":
            orbital = [app for app in self.apps if app.get("orbit_of") and not app.get("system_role")]
            QMessageBox.information(
                self, "Modules en orbite",
                f"{len(orbital)} module(s) ou outil(s) personnel(s) sont actuellement rattachés à une orbite.\n\n"
                "La déconnexion par boule orbitale sera la prochaine couche d'interaction.",
            )
            return

        if role == "common_services":
            QMessageBox.information(
                self, "Services Communs",
                "Cette couche prépare les fichiers, paramètres, ressources, mises à jour et messages partagés entre univers.",
            )
            return

        if role == "wormholes":
            self.open_existence_center("wormholes")
            return

        if role == "gravity":
            QMessageBox.information(
                self, "Gravité",
                "La gravité décrira les dépendances, proximités, appartenances et services partagés entre modules.",
            )
            return

        if role == "resource_index":
            QMessageBox.information(
                self, "Centralisation Ressources",
                "Existence indexe les ressources communes pour les retrouver et les partager sans forcément les posséder.",
            )
            return

        QMessageBox.information(self, "Module système", "Ce module prépare le terrain commun d'Existence.")


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

def main():
    # Empêche KDE/Kvantum d'injecter ses couleurs par-dessus le QSS
    os.environ["QT_QPA_PLATFORMTHEME"] = ""
    os.environ.pop("QT_STYLE_OVERRIDE", None)

    app = QApplication(sys.argv)
    # Ctrl+C dans le terminal : fermeture propre au lieu d'une exception au
    # milieu d'un dessin (painter laissé ouvert → SIGSEGV).
    import signal
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    _sigint_pump = QTimer()
    _sigint_pump.timeout.connect(lambda: None)   # rend la main à Python pour traiter le signal
    _sigint_pump.start(250)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet("")  # vide tout stylesheet injecté par la plateforme
    app.setApplicationName("Existence")
    app.setApplicationVersion(APP_VERSION)

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(C["bg"]))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Base,            QColor(C["surface"]))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(C["bg2"]))
    pal.setColor(QPalette.ColorRole.Text,            QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Button,          QColor(C["surface"]))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(C["purple"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    pal.setColor(QPalette.ColorRole.Mid,             QColor(C["surface_h"]))
    pal.setColor(QPalette.ColorRole.Midlight,        QColor(C["surface"]))
    pal.setColor(QPalette.ColorRole.Light,           QColor(C["border"]))
    pal.setColor(QPalette.ColorRole.Dark,            QColor(C["bg"]))
    pal.setColor(QPalette.ColorRole.Shadow,          QColor(C["bg"]))
    app.setPalette(pal)

    win = GalaxyHub()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
