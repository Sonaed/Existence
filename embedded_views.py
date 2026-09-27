"""Providers de vues natives pour la Workplace Wayland d'Existence."""

from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
import tempfile
import importlib.util
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox, QSizePolicy
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtSvg import QSvgRenderer

from existence_ipc import ProcessEndpoint
from existence_paths import app_dir, native


NEBULA_ROOT = app_dir("nebula")
COSMOS_ROOT = app_dir("cosmos")
ATLAS_ADAPTER = Path(native("atlas", "AtlasExistenceAdapter", "build_atlas"))
STARDUST_ROOT = app_dir("stardust")


def create_nebula_view(parent: QWidget) -> QWidget:
    """Construit la vraie interface Nebula dans le processus Existence.

    Wayland n'autorise pas l'import d'une surface appartenant à un autre
    processus. Ce provider charge donc le frontend Nebula comme composant Qt
    dans le processus de la Workplace ; son moteur et ses documents restent
    isolés derrière l'API de l'univers.
    """
    root = str(NEBULA_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ["EXISTENCE_EMBEDDED_VIEW"] = "1"
    from CORE.application import CreativeSystem

    window = CreativeSystem()
    window.setWindowFlags(Qt.WindowType.Widget)
    window.setParent(parent)
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    window.setObjectName("NebulaEmbeddedView")
    return window


def create_cosmos_view(parent: QWidget) -> QWidget:
    """Construit la vue WebEngine de Cosmos dans la Workplace Wayland."""
    view = QWebEngineView(parent)
    view.setObjectName("CosmosEmbeddedView")
    settings = view.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
    view.load(QUrl.fromLocalFile(str(COSMOS_ROOT / "index.html")))
    return view


class AtlasEmbeddedView(QWidget):
    """Vue Qt Wayland d'Atlas, pilotée par son moteur Existence headless."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("AtlasEmbeddedView")
        self._runtime = Path(tempfile.mkdtemp(prefix="existence-atlas-view-"))
        self._endpoint = ProcessEndpoint([str(ATLAS_ADAPTER), "--stdio"])
        self._endpoint.request("handshake")

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel("ATLAS · vue Wayland embarquée")
        title.setStyleSheet("font-weight:700;padding:6px;")
        toolbar.addWidget(title)
        toolbar.addStretch()
        export_button = QPushButton("Actualiser le document")
        export_button.clicked.connect(self.refresh_document)
        toolbar.addWidget(export_button)
        self.singularize_button = QPushButton("Singulariser")
        self.singularize_button.clicked.connect(self.singularize_current)
        self.singularize_button.setVisible(False)
        toolbar.addWidget(self.singularize_button)
        layout.addLayout(toolbar)

        self.status = QLabel("Backend Atlas connecté")
        self.status.setStyleSheet("color:#9090CC;padding:4px;")
        layout.addWidget(self.status)
        self.canvas = QSvgWidget()
        self.canvas.setMinimumSize(420, 420)
        layout.addWidget(self.canvas, 1)
        self.refresh_document()

    @staticmethod
    def _attached_modules(parent_id: str) -> list[str]:
        """Lit l'état d'orbite publié par Existence sans lancer le module."""
        config = Path.home() / ".config" / "existence" / "apps.json"
        try:
            apps = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [
            str(app.get("name", app.get("id", "module")))
            for app in apps
            if (app.get("orbit_of") == parent_id or parent_id in (app.get("orbits") or []))
            and app.get("app_kind") == "orbital_module"
        ]

    def refresh_existence_modules(self) -> None:
        """Actualise la présence des modules branchés sur Atlas."""
        modules = self._attached_modules("atlas")
        singularity_connected = any(name.lower() == "singularity".lower() for name in modules)
        self.singularize_button.setVisible(singularity_connected)
        self.singularize_button.setEnabled(singularity_connected)
        suffix = (
            " · Modules orbitaux : " + ", ".join(modules)
            if modules else " · Aucun module orbital"
        )
        self.status.setText("Backend Atlas connecté" + suffix)

    def singularize_current(self) -> None:
        """Exporte le document SVG courant via Singularity sans son interface."""
        if not self.singularize_button.isEnabled() or not self.canvas.isVisible():
            return
        destination, _ = QFileDialog.getSaveFileName(
            self, "Singulariser en WebP", "", "WebP (*.webp)"
        )
        if not destination:
            return
        if not destination.lower().endswith(".webp"):
            destination += ".webp"

        source = self._runtime / "atlas-document.svg"
        singularity = app_dir("singularity") / "webready.py"
        temporary = None
        try:
            renderer = QSvgRenderer(str(source))
            size = renderer.defaultSize()
            image = QImage(max(1, size.width()), max(1, size.height()), QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
                temporary = Path(handle.name)
            if not image.save(str(temporary), "PNG"):
                raise RuntimeError("Atlas n'a pas pu préparer le document courant.")
            result = subprocess.run(
                [sys.executable, str(singularity), "--headless", str(temporary), destination],
                cwd=str(singularity.parent), capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Singularity a refusé l'export.")
            self.status.setText(f"Singularisé : {destination}")
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            QMessageBox.warning(self, "Singularity", f"Export impossible : {exc}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def refresh_document(self) -> None:
        output = self._runtime / "atlas-document.svg"
        response = self._endpoint.request("produce_resource", output_path=str(output))
        if response.ok and output.exists():
            self.canvas.load(str(output))
            self.status.setText("Backend Atlas connecté · document resource://existence/atlas")
            self.refresh_existence_modules()
        else:
            self.status.setText(f"Atlas : {response.body.get('error', 'erreur de production')}")

    def closeEvent(self, event):
        self._endpoint.close()
        shutil.rmtree(self._runtime, ignore_errors=True)
        super().closeEvent(event)


def create_atlas_view(parent: QWidget) -> QWidget:
    if not ATLAS_ADAPTER.exists():
        raise FileNotFoundError(f"Atlas adapter absent : {ATLAS_ADAPTER}")
    return AtlasEmbeddedView(parent)


def create_stardust_view(parent: QWidget, resource_registry=None, module_registry=None) -> QWidget:
    """Construit StarDust comme univers embarqué d'Existence.

    Le Creator reste dans son univers dédié, tandis que les publications passent
    par le registre de ressources possédé par Existence.
    """
    root = str(STARDUST_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    # Charge toujours le fichier courant : Existence peut rester ouvert
    # pendant qu'un nouveau build StarDust est installé.
    module_name = f"stardust_runtime_{uuid.uuid4().hex}"
    module_path = STARDUST_ROOT / "main.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger StarDust depuis {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    StarDust = module.StarDust

    # Existence possède les modules Creator et leur interface : on transmet à
    # StarDust les manifests (dont le point d'entrée de l'interface) et
    # l'état branché/débranché ; StarDust s'adapte.
    connected = {}
    module_manifests = {}
    if module_registry is not None:
        bindings = module_registry.resource_bindings("stardust")
        bound = {b.resource_kind for b in bindings if b.access in {"write", "read_write"}}
        candidates = {"fusion_creator": "blend_definition"}
        for manifest in module_registry.creators_for("stardust") if hasattr(module_registry, "creators_for") else []:
            candidates[manifest.id] = manifest.produces
        for module_id, kind in candidates.items():
            manifest = module_registry.manifest(module_id)
            if manifest is None:
                continue
            module_manifests[module_id] = manifest.to_dict()
            connected[module_id] = kind in bound
    try:
        window = StarDust(
            resource_registry=resource_registry,
            connected_creators=connected,
            module_manifests=module_manifests,
            module_registry=module_registry,
        )
    except TypeError:   # build StarDust antérieur à existence.creator.v1
        window = StarDust(
            resource_registry=resource_registry,
            connected_creators={"fusion_creator": connected.get("fusion_creator", False)},
            module_manifests=module_manifests,
        )
    window.setWindowFlags(Qt.WindowType.Widget)
    window.setParent(parent)
    window.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    window.setMinimumSize(1100, 700)
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    window.setObjectName("StarDustEmbeddedView")
    return window
