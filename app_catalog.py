"""Centre Existence : catalogue d'apps / modules + vue des Ressources.

Ouvert par un double-clic sur l'astre Existence (ou sur l'Installateur).
Onglets en haut :
    • Catalogue  — univers et modules : installer, mettre à jour, ouvrir,
                    brancher / débrancher (les modules gravitent autour d'un hôte)
    • Ressources — ce que contient la bibliothèque centrale, par app et par type

Le catalogue fusionne :
    1. les astres connus d'Existence (DEFAULT_APPS du hub) ;
    2. ``existence_catalog.json`` à côté de ce fichier (dépôts git, versions) ;
    3. un catalogue distant optionnel (``$EXISTENCE_CATALOG_URL`` ou le champ
       ``remote`` du fichier local) — pour quand les apps seront publiées sur GitHub.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QProcess, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QStackedWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

HERE = Path(__file__).resolve().parent
LOCAL_CATALOG = HERE / "existence_catalog.json"
INSTALL_ROOT = Path(os.environ.get("EXISTENCE_APPS_HOME", "") or
                    Path.home() / ".local" / "share" / "existence" / "apps")

# Rôles système : ne sont pas des produits du catalogue.
_HIDDEN_KINDS = {"environment", "service", "template"}

COLORS = {
    "bg": "#080818", "bg2": "#0C0C20", "surface": "#111128", "surface_h": "#181838",
    "border": "#1E1E45", "border_h": "#3A3A80", "text": "#E8E8FF", "text2": "#9090CC",
    "text3": "#5A5A90", "purple": "#7C3AED", "green": "#10B981", "orange": "#F97316",
    "cyan": "#06B6D4", "red": "#EF4444",
}
C = COLORS


# ══════════════════════════════════════════════════════════════
#  Données du catalogue
# ══════════════════════════════════════════════════════════════

def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _fetch_remote(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=4) as response:  # noqa: S310 (URL choisie par l'utilisateur)
            data = json.loads(response.read().decode("utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_catalog(known_apps: list[dict], remote: bool = True) -> list[dict]:
    """Retourne les entrées de catalogue (univers + modules) fusionnées."""
    entries: dict[str, dict] = {}
    for app in known_apps:
        kind = app.get("app_kind", "universe")
        if app.get("system_role") or kind in _HIDDEN_KINDS:
            continue
        entries[app["id"]] = {
            "id": app["id"], "name": app.get("name", app["id"]),
            "description": app.get("description", ""),
            "icon": app.get("icon_emoji", "✦"), "accent": app.get("accent_color", C["purple"]),
            "version": app.get("version", ""), "git_url": app.get("git_url", ""),
            "kind": "module" if kind == "orbital_module" else "universe",
            "host": app.get("orbit_of", ""), "bundled": app.get("install_type") == "system",
        }
    local = _read_json(LOCAL_CATALOG)
    sources = [local]
    url = os.environ.get("EXISTENCE_CATALOG_URL", "").strip() or str(local.get("remote", "")).strip()
    if remote and url:
        sources.append(_fetch_remote(url))
    for source in sources:
        for item in source.get("apps", []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            merged = entries.setdefault(item["id"], {"id": item["id"], "kind": "universe"})
            merged.update({k: v for k, v in item.items() if v not in (None, "")})
    for entry in entries.values():
        entry.setdefault("name", entry["id"])
        entry.setdefault("icon", "✦")
        entry.setdefault("accent", C["purple"])
        entry.setdefault("description", "")
        entry.setdefault("standalone", False)
        entry.setdefault("launch", ["python", "main.py"])
    return sorted(entries.values(), key=lambda e: (e["kind"] != "universe", e["name"].lower()))


def installed_version(app: dict | None) -> str:
    return (app or {}).get("version", "")


# ══════════════════════════════════════════════════════════════
#  Widgets
# ══════════════════════════════════════════════════════════════

def _button(text: str, primary: bool = False, danger: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    colour = C["red"] if danger else (C["purple"] if primary else C["surface_h"])
    border = colour if (primary or danger) else C["border_h"]
    button.setStyleSheet(
        f"QPushButton{{background:{colour};color:{C['text']};border:1px solid {border};"
        f"border-radius:7px;padding:5px 12px;font-size:12px;}}"
        f"QPushButton:hover{{border-color:{C['text2']};}}"
        f"QPushButton:disabled{{background:{C['surface']};color:{C['text3']};border-color:{C['border']};}}"
    )
    return button


def _badge(text: str, colour: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color:{colour};border:1px solid {colour};border-radius:8px;padding:1px 7px;"
        f"font-size:10px;background:transparent;"
    )
    return label


class CatalogCard(QFrame):
    def __init__(self, entry: dict, page: "CatalogPage") -> None:
        super().__init__()
        self.entry = entry
        self.page = page
        self.setObjectName("card")
        self.setMinimumHeight(150)
        self.setStyleSheet(
            f"QFrame#card{{background:{C['surface']};border:1px solid {C['border']};border-radius:12px;}}"
            f"QFrame#card:hover{{border-color:{entry['accent']};}}"
            f"QLabel{{background:transparent;}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        head = QHBoxLayout()
        icon = QLabel(entry["icon"])
        icon.setFixedSize(38, 38)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"background:{entry['accent']}33;border:1px solid {entry['accent']};"
            f"border-radius:19px;font-size:18px;color:{entry['accent']};"
        )
        head.addWidget(icon)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        name = QLabel(entry["name"])
        name.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:600;")
        titles.addWidget(name)
        self.sub = QLabel()
        self.sub.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        titles.addWidget(self.sub)
        head.addLayout(titles, 1)
        self.badges = QHBoxLayout()
        self.badges.setSpacing(4)
        head.addLayout(self.badges)
        layout.addLayout(head)

        description = QLabel(entry["description"] or "—")
        description.setWordWrap(True)
        description.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        layout.addWidget(description, 1)

        self.status = QLabel()
        self.status.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        layout.addWidget(self.status)

        self.actions = QHBoxLayout()
        self.actions.setSpacing(6)
        layout.addLayout(self.actions)
        self.refresh()

    def _clear(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self) -> None:
        entry, page = self.entry, self.page
        app = page.app(entry["id"])
        installed = bool(app and app.get("installed"))
        busy = page.busy.get(entry["id"])

        self._clear(self.badges)
        if entry["kind"] == "module":
            hosts = [page.app_name(h) for h in page.hosts(entry["id"])]
            self.badges.addWidget(_badge("Module", C["cyan"]))
            if entry.get("standalone"):
                self.badges.addWidget(_badge("Fonctionne seul", C["orange"]))
            if hosts:
                self.sub.setText("Branché sur " + ", ".join(hosts))
            elif installed:
                self.sub.setText("Rangé dans la boîte à outils")
            else:
                self.sub.setText(f"Conçu pour {page.app_name(entry.get('host', ''))}" if entry.get("host") else "Module")
        else:
            self.badges.addWidget(_badge("Univers", C["purple"]))
            self.sub.setText(f"{entry['name']} {entry['version']}" if entry.get("version") else "")

        self._clear(self.actions)
        if busy:
            self.status.setText(busy)
            self.actions.addStretch(1)
            return

        source = entry.get("git_url", "")
        if installed:
            local = installed_version(app)
            remote = entry.get("version", "")
            packaged = str((app or {}).get("working_dir", "")).startswith("/usr/share/existence/")
            update = bool(remote and local and remote != local and source) and not packaged
            where = ("paquet système · mises à jour via pacman / apt" if packaged else
                     (app or {}).get("working_dir") or ("intégré à Existence" if entry.get("bundled") else ""))
            self.status.setText(("● Installé" + (f" · {entry['name']} {local}" if local else "")
                                 + (f" · mise à jour {remote}" if update else "")
                                 + (f"  —  {where}" if where else "")))
            self.status.setStyleSheet(f"color:{C['green']};font-size:11px;")
            if entry["kind"] == "module":
                plug = _button("Brancher sur…", primary=not page.is_plugged(entry["id"]))
                plug.clicked.connect(lambda: page.plug_menu(entry, plug))
                self.actions.addWidget(plug)
                if page.is_plugged(entry["id"]):
                    store = _button("Ranger 🧰")
                    store.setToolTip("Débrancher de tous les univers et ranger dans la boîte à outils")
                    store.clicked.connect(lambda: page.store(entry))
                    self.actions.addWidget(store)
                if entry.get("standalone") and (app or {}).get("exec_path"):
                    alone = _button("Ouvrir seul")
                    alone.clicked.connect(lambda: page.open_app(entry))
                    self.actions.addWidget(alone)
            elif (app or {}).get("exec_path"):
                open_button = _button("Ouvrir", primary=True)
                open_button.clicked.connect(lambda: page.open_app(entry))
                self.actions.addWidget(open_button)
            if not packaged and (update or (source and (app or {}).get("install_type") == "catalog")):
                upd = _button("Mettre à jour")
                upd.clicked.connect(lambda: page.update_app(entry))
                self.actions.addWidget(upd)
            self.actions.addStretch(1)
            if not entry.get("bundled") and not packaged:
                remove = _button("Désinstaller", danger=True)
                remove.clicked.connect(lambda: page.uninstall(entry))
                self.actions.addWidget(remove)
        else:
            self.status.setStyleSheet(f"color:{C['text3']};font-size:11px;")
            if source or entry.get("bundled"):
                self.status.setText("Disponible" + (f" · {entry['name']} {entry['version']}" if entry.get("version") else ""))
                install = _button("Installer", primary=True)
                install.clicked.connect(lambda: page.install(entry))
                self.actions.addWidget(install)
            else:
                self.status.setText("Bientôt disponible — pas encore publié")
                soon = _button("Installer")
                soon.setEnabled(False)
                self.actions.addWidget(soon)
            self.actions.addStretch(1)


class CatalogPage(QWidget):
    def __init__(self, hub: Any) -> None:
        super().__init__()
        self.hub = hub
        self.busy: dict[str, str] = {}
        self.cards: list[CatalogCard] = []
        self._process: QProcess | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher une app ou un module…")
        self.search.textChanged.connect(self._filter)
        bar.addWidget(self.search, 1)
        manual = _button("Ajouter manuellement…")
        manual.setToolTip("Déclarer une app locale qui n'est pas dans le catalogue")
        manual.clicked.connect(self._manual_add)
        bar.addWidget(manual)
        reload_button = _button("↻ Actualiser")
        reload_button.clicked.connect(lambda: self.reload(remote=True))
        bar.addWidget(reload_button)
        layout.addLayout(bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;}")
        self.body = QWidget()
        self.body.setStyleSheet("background:transparent;")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 8, 6, 8)
        self.body_layout.setSpacing(10)
        scroll.setWidget(self.body)
        layout.addWidget(scroll, 1)
        self.reload(remote=True)

    # ── accès au hub ──
    def app(self, app_id: str) -> dict | None:
        return next((a for a in self.hub.apps if a.get("id") == app_id), None)

    def app_name(self, app_id: str) -> str:
        app = self.app(app_id)
        return app.get("name", app_id) if app else app_id

    def hosts(self, app_id: str) -> list[str]:
        app = self.app(app_id) or {}
        hosts = [h for h in (app.get("orbits") or []) if h]
        if app.get("orbit_of") and app["orbit_of"] not in hosts:
            hosts.insert(0, app["orbit_of"])
        return hosts

    def is_plugged(self, app_id: str) -> bool:
        app = self.app(app_id) or {}
        return bool(app.get("installed") and self.hosts(app_id)
                    and app.get("app_kind") == "orbital_module"
                    and app.get("lifecycle_state", "available") != "closed")

    def universes(self) -> list[dict]:
        return [a for a in self.hub.apps if a.get("installed", True)
                and (a.get("app_kind") == "universe" or a.get("standalone") or a.get("id") in {"nova", "singularity"})]

    def _commit(self) -> None:
        self.hub.cfg.save(self.hub.apps)
        for hook in ("_refresh_stardust_bindings", "_refresh"):
            fn = getattr(self.hub, hook, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
        for card in self.cards:
            card.refresh()

    # ── construction ──
    def reload(self, remote: bool = False) -> None:
        self.catalog = load_catalog(self.hub.apps, remote=remote)
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards = []
        for title, kind, hint in (
            ("Univers", "universe", "Applications autonomes de l'écosystème"),
            ("Modules", "module", "Se branchent sur un univers hôte et y apportent leur interface"),
        ):
            header = QLabel(f"<b style='font-size:15px;color:{C['text']}'>{title}</b>"
                            f"&nbsp;&nbsp;<span style='color:{C['text3']};font-size:11px'>{hint}</span>")
            header.setStyleSheet("background:transparent;padding-top:6px;")
            self.body_layout.addWidget(header)
            grid_host = QWidget()
            grid_host.setStyleSheet("background:transparent;")
            grid = QGridLayout(grid_host)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(10)
            items = [e for e in self.catalog if e["kind"] == kind]
            for index, entry in enumerate(items):
                card = CatalogCard(entry, self)
                self.cards.append(card)
                grid.addWidget(card, index // 2, index % 2)
            if not items:
                grid.addWidget(QLabel("—"), 0, 0)
            self.body_layout.addWidget(grid_host)
        self.body_layout.addStretch(1)
        self._filter(self.search.text())

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for card in self.cards:
            haystack = f"{card.entry['name']} {card.entry['description']} {card.entry['id']}".lower()
            card.setVisible(not needle or needle in haystack)

    def _manual_add(self) -> None:
        fn = getattr(self.hub, "_add_app", None)
        if callable(fn):
            fn()
            self.reload()

    # ── actions ──
    def open_app(self, entry: dict) -> None:
        app = self.app(entry["id"])
        if app:
            launch = dict(app)
            if entry.get("standalone"):
                launch["_standalone"] = True
            self.hub._launch(launch)

    def plug_menu(self, entry: dict, anchor: QWidget) -> None:
        from PySide6.QtWidgets import QMenu
        menu = QMenu(anchor)
        current = set(self.hosts(entry["id"]))
        preferred = entry.get("host", "")
        from modules.compat import is_compatible
        choices = [u for u in self.universes() if is_compatible(self.app(entry["id"]) or entry["id"], u["id"], self.hub.apps)]
        if not choices:
            menu.addAction("Aucun univers compatible").setEnabled(False)
        for universe in sorted(choices, key=lambda a: (a["id"] != preferred, a.get("name", ""))):
            uid = universe["id"]
            action = menu.addAction(("✓  " if uid in current else "    ") + universe.get("name", uid)
                                    + ("  (conseillé)" if uid == preferred else ""))
            action.triggered.connect(lambda _=False, u=uid: self.toggle_host(entry, u))
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def toggle_host(self, entry: dict, universe_id: str) -> None:
        if self.app(entry["id"]) is None:
            return
        if universe_id in self.hosts(entry["id"]):
            self.hub.plug_module(entry["id"], universe_id, "__toolbox__", True)
        else:
            self.hub.plug_module(entry["id"], "", universe_id, False)
        self._after_hub_change()

    def store(self, entry: dict) -> None:
        self.hub.plug_module(entry["id"], "", "__toolbox__", True)
        self._after_hub_change()

    def _after_hub_change(self) -> None:
        for card in self.cards:
            card.refresh()

    def install(self, entry: dict) -> None:
        app = self.app(entry["id"])
        if entry.get("bundled") and not entry.get("git_url"):
            if app:
                app["installed"] = True
                app["lifecycle_state"] = "available"
                self._commit()
                if entry["kind"] == "module" and not self.hosts(entry["id"]) and entry.get("host"):
                    self.hub.plug_module(entry["id"], "", entry["host"], False)
                    self._after_hub_change()
            return
        target = INSTALL_ROOT / entry["id"]
        if target.exists() and any(target.iterdir()):
            self._finish_install(entry, target)
            return
        if shutil.which("git") is None:
            QMessageBox.warning(self, "Installation", "git est introuvable sur ce système.")
            return
        INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
        args = ["clone", "--depth", "1"]
        if entry.get("branch"):
            args += ["--branch", entry["branch"]]
        args += [entry["git_url"], str(target)]
        self._run(entry, args, "Téléchargement…", lambda ok: ok and self._finish_install(entry, target))

    def update_app(self, entry: dict) -> None:
        app = self.app(entry["id"]) or {}
        folder = Path(app.get("working_dir") or INSTALL_ROOT / entry["id"])
        if not (folder / ".git").exists():
            QMessageBox.information(self, "Mise à jour",
                                    f"{entry['name']} n'est pas un dépôt git ({folder}).\n"
                                    "Mets-le à jour à la main ou réinstalle-le depuis le catalogue.")
            return
        self._run(entry, ["-C", str(folder), "pull", "--ff-only"], "Mise à jour…",
                  lambda ok: ok and self._finish_install(entry, folder))

    def _run(self, entry: dict, args: list[str], label: str, done: Callable[[bool], Any]) -> None:
        if self._process is not None:
            QMessageBox.information(self, "Catalogue", "Une installation est déjà en cours.")
            return
        self.busy[entry["id"]] = label
        self._refresh_card(entry["id"])
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process = process

        def finished(code, _status):
            output = bytes(process.readAll()).decode("utf-8", "replace")
            self._process = None
            self.busy.pop(entry["id"], None)
            ok = code == 0
            if not ok:
                QMessageBox.warning(self, "Échec", f"{entry['name']} :\n\n{output[-1500:]}")
            done(ok)
            self._refresh_card(entry["id"])

        process.finished.connect(finished)
        process.start("git", args)

    def _refresh_card(self, app_id: str) -> None:
        for card in self.cards:
            if card.entry["id"] == app_id:
                card.refresh()

    def _finish_install(self, entry: dict, folder: Path) -> None:
        app = self.app(entry["id"])
        if app is None:
            app = {"id": entry["id"], "name": entry["name"], "description": entry["description"],
                   "category": entry.get("category", "Création"), "icon_emoji": entry["icon"],
                   "icon_path": "", "accent_color": entry["accent"], "tags": [],
                   "app_kind": "orbital_module" if entry["kind"] == "module" else "universe",
                   "orbit_of": entry.get("host", "") if entry["kind"] == "module" else "",
                   "orbits": [entry["host"]] if entry["kind"] == "module" and entry.get("host") else []}
            self.hub.apps.append(app)
        launch = list(entry.get("launch") or ["python", "main.py"])
        manifest = folder / "existence-manifest.json"
        app.update({
            "installed": True, "install_type": "catalog", "git_url": entry.get("git_url", ""),
            "working_dir": str(folder), "exec_path": launch[0], "exec_args": launch[1:],
            "version": entry.get("version", app.get("version", "")),
            "lifecycle_state": "available", "installed_at": time.time(),
        })
        if manifest.exists():
            app["manifest_path"] = str(manifest)
        self._commit()
        notes = []
        if (folder / "requirements.txt").exists():
            notes.append(f"Dépendances Python : pip install -r \"{folder / 'requirements.txt'}\"")
        if (folder / "CMakeLists.txt").exists() or (folder / "CPP_CORE").exists():
            notes.append("Cette app contient du C++ : pense à la compiler.")
        if notes:
            QMessageBox.information(self, f"{entry['name']} installé", "\n\n".join(notes))

    def uninstall(self, entry: dict) -> None:
        app = self.app(entry["id"])
        if not app:
            return
        folder = Path(app.get("working_dir") or "")
        owned = app.get("install_type") == "catalog" and INSTALL_ROOT in folder.parents
        message = f"Retirer « {entry['name']} » d'Existence ?"
        message += (f"\n\nSon dossier sera supprimé :\n{folder}" if owned
                    else "\n\nLes fichiers de l'app ne sont pas touchés.")
        reply = QMessageBox.question(self, "Désinstaller", message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        if owned:
            shutil.rmtree(folder, ignore_errors=True)
        app["installed"] = False
        app["lifecycle_state"] = "closed"
        if owned:
            app["exec_path"] = ""
            app["working_dir"] = ""
        self._commit()


# ══════════════════════════════════════════════════════════════
#  Vue des ressources
# ══════════════════════════════════════════════════════════════

class ResourcesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        from modules.resource_center.library import APP_LABELS, SharedLibrary
        self.library = SharedLibrary()
        self.labels = APP_LABELS

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher une ressource…")
        self.app_combo = QComboBox()
        self.app_combo.addItem("Toutes les apps", None)
        for app_id, label in APP_LABELS.items():
            self.app_combo.addItem(f"Utilisable dans {label}", app_id)
        self.kind_combo = QComboBox()
        folder = _button("Ouvrir le dossier")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.library.root))))
        refresh = _button("↻")
        refresh.clicked.connect(self.reload)
        bar.addWidget(self.search, 1)
        bar.addWidget(self.app_combo)
        bar.addWidget(self.kind_combo)
        bar.addWidget(folder)
        bar.addWidget(refresh)
        layout.addLayout(bar)

        self.summary = QLabel()
        self.summary.setStyleSheet(f"color:{C['text2']};font-size:12px;padding:6px 2px;background:transparent;")
        layout.addWidget(self.summary)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Nom", "Type", "Utilisable dans", "Version", "Modifié"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(self._reveal)
        self.tree.setStyleSheet(
            f"QTreeWidget{{background:{C['surface']};alternate-background-color:{C['bg2']};"
            f"border:1px solid {C['border']};border-radius:8px;color:{C['text']};font-size:12px;}}"
            f"QHeaderView::section{{background:{C['bg2']};color:{C['text2']};border:none;padding:6px;}}"
            f"QTreeWidget::item{{padding:4px;}}"
            f"QTreeWidget::item:selected{{background:{C['border_h']};}}"
        )
        layout.addWidget(self.tree, 1)

        self.search.textChanged.connect(self._populate)
        self.app_combo.currentIndexChanged.connect(self._populate)
        self.kind_combo.currentIndexChanged.connect(self._populate)
        self.reload()

    def reload(self) -> None:
        try:
            self._entries = self.library.entries()
        except OSError:
            self._entries = []
        current = self.kind_combo.currentData()
        self.kind_combo.blockSignals(True)
        self.kind_combo.clear()
        self.kind_combo.addItem("Tous les types", None)
        for kind in sorted({e["kind"] for e in self._entries}):
            count = sum(1 for e in self._entries if e["kind"] == kind)
            self.kind_combo.addItem(f"{kind.replace('_', ' ')} ({count})", kind)
        index = self.kind_combo.findData(current)
        self.kind_combo.setCurrentIndex(max(0, index))
        self.kind_combo.blockSignals(False)
        self._populate()

    def _populate(self, *_args) -> None:
        app = self.app_combo.currentData()
        kind = self.kind_combo.currentData()
        needle = self.search.text().strip().lower()
        self.tree.clear()
        shown = 0
        for entry in self._entries:
            if app and app not in entry["apps"]:
                continue
            if kind and entry["kind"] != kind:
                continue
            if needle and needle not in f"{entry['name']} {entry['key']}".lower():
                continue
            path = Path(entry["path"])
            try:
                modified = time.strftime("%d/%m/%Y %H:%M", time.localtime(path.stat().st_mtime))
            except OSError:
                modified = ""
            apps = ", ".join(self.labels.get(a, a) for a in entry["apps"])
            item = QTreeWidgetItem([entry["name"], entry["kind"].replace("_", " "), apps,
                                    str(entry.get("version", "")), modified])
            item.setToolTip(0, str(path))
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            self.tree.addTopLevelItem(item)
            shown += 1
        total = len(self._entries)
        kinds = len({e["kind"] for e in self._entries})
        self.summary.setText(f"{shown} affichée(s) · {total} ressource(s) dans {kinds} type(s) · {self.library.root}")

    def _reveal(self, item: QTreeWidgetItem, _column: int) -> None:
        path = Path(item.data(0, Qt.ItemDataRole.UserRole))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))



# ══════════════════════════════════════════════════════════════
#  Wormholes
# ══════════════════════════════════════════════════════════════

class WormholesPage(QWidget):
    def __init__(self, hub: Any) -> None:
        super().__init__()
        from modules.wormhole import Wormhole, WORMHOLE_APPS
        self.hole = Wormhole("existence")
        self.names = {k: v["name"] for k, v in WORMHOLE_APPS.items()}
        self.names.update({a.get("id"): a.get("name", a.get("id")) for a in getattr(hub, "apps", [])})
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        intro = QLabel(
            "Un wormhole transporte un calque ou une image d'une app à l'autre. "
            "Un <b>lien en direct</b> garde les deux côtés synchronisés : chaque modification "
            "d'un côté arrive automatiquement de l'autre. Depuis Nebula : Image ▸ Wormhole ⇄. "
            "Si l'app destinataire est fermée, Existence l'ouvre.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{C['text2']};font-size:12px;background:transparent;padding:4px 2px 8px;")
        layout.addWidget(intro)

        self.apps_row = QLabel()
        self.apps_row.setStyleSheet(f"color:{C['text']};font-size:12px;background:transparent;")
        layout.addWidget(self.apps_row)

        header = QHBoxLayout()
        title = QLabel("<b>Liens en direct</b>")
        title.setStyleSheet(f"color:{C['text']};font-size:14px;background:transparent;padding-top:8px;")
        header.addWidget(title)
        header.addStretch(1)
        self.unlink_button = _button("Délier", danger=True)
        self.unlink_button.clicked.connect(self._unlink)
        header.addWidget(self.unlink_button)
        refresh = _button("↻")
        refresh.clicked.connect(self.reload)
        header.addWidget(refresh)
        layout.addLayout(header)

        tree_style = (
            f"QTreeWidget{{background:{C['surface']};alternate-background-color:{C['bg2']};"
            f"border:1px solid {C['border']};border-radius:8px;color:{C['text']};font-size:12px;}}"
            f"QHeaderView::section{{background:{C['bg2']};color:{C['text2']};border:none;padding:6px;}}"
            f"QTreeWidget::item{{padding:4px;}}QTreeWidget::item:selected{{background:{C['border_h']};}}")
        self.links = QTreeWidget()
        self.links.setHeaderLabels(["Nom", "Entre", "Révision", "Dernière modif. par", "Quand"])
        self.links.setRootIsDecorated(False)
        self.links.setAlternatingRowColors(True)
        self.links.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.links.setStyleSheet(tree_style)
        layout.addWidget(self.links, 2)

        title = QLabel("<b>Derniers transferts</b>")
        title.setStyleSheet(f"color:{C['text']};font-size:14px;background:transparent;padding-top:10px;")
        layout.addWidget(title)
        self.log = QTreeWidget()
        self.log.setHeaderLabels(["Quand", "Événement", "Détail"])
        self.log.setRootIsDecorated(False)
        self.log.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.log.setStyleSheet(tree_style)
        layout.addWidget(self.log, 2)

        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.reload)
        self._timer.start()
        self.reload()

    def _name(self, app_id: str) -> str:
        return self.names.get(app_id, app_id)

    def reload(self) -> None:
        parts = []
        for app_id in ("nebula", "nova", "singularity"):
            alive = self.hole.is_alive(app_id)
            pending = self.hole.pending(app_id)
            dot = f"<span style='color:{C['green'] if alive else C['text3']}'>●</span>"
            parts.append(f"{dot} {self._name(app_id)}" + (f" · {pending} en attente" if pending else ""))
        self.apps_row.setText("&nbsp;&nbsp;&nbsp;".join(parts))
        selected = self.links.currentItem().data(0, Qt.ItemDataRole.UserRole) if self.links.currentItem() else None
        self.links.clear()
        for record in sorted(self.hole.links("*"), key=lambda r: -float(r.get("updated_at", 0))):
            when = time.strftime("%d/%m %H:%M:%S", time.localtime(float(record.get("updated_at", 0))))
            item = QTreeWidgetItem([record.get("name", ""), " ⇄ ".join(self._name(a) for a in record.get("apps", [])),
                                    str(record.get("rev", 1)), self._name(record.get("writer", "")), when])
            item.setData(0, Qt.ItemDataRole.UserRole, record["id"])
            self.links.addTopLevelItem(item)
            if record["id"] == selected:
                self.links.setCurrentItem(item)
        if self.links.topLevelItemCount() == 0:
            self.links.addTopLevelItem(QTreeWidgetItem(["Aucun lien — Nebula ▸ Image ▸ Wormhole ⇄ ▸ Lier le calque en direct"]))
        self.log.clear()
        labels = {"send": "Envoi", "receive": "Réception", "unlink": "Lien retiré"}
        for event in self.hole.recent(30):
            when = time.strftime("%d/%m %H:%M:%S", time.localtime(float(event.get("time", 0))))
            if event.get("event") == "send":
                detail = (f"{self._name(event.get('app', ''))} → {self._name(event.get('target', ''))} : "
                          f"{event.get('name', '')}" + (" (lien en direct)" if event.get("live") else ""))
            elif event.get("event") == "receive":
                detail = f"{self._name(event.get('app', ''))} a reçu {event.get('count', 1)} envoi(s)"
            else:
                detail = event.get("name", "")
            self.log.addTopLevelItem(QTreeWidgetItem([when, labels.get(event.get("event"), event.get("event", "")), detail]))

    def _unlink(self) -> None:
        item = self.links.currentItem()
        link_id = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if link_id:
            self.hole.unlink(link_id)
            self.reload()

# ══════════════════════════════════════════════════════════════
#  Fenêtre
# ══════════════════════════════════════════════════════════════

class ExistenceCenter(QDialog):
    TABS = (("catalog", "Catalogue d'apps"), ("resources", "Ressources"), ("wormholes", "Wormholes"))

    def __init__(self, hub: Any, tab: str = "catalog") -> None:
        super().__init__(hub)
        self.setWindowTitle("Existence")
        self.resize(980, 700)
        self.setStyleSheet(
            f"QDialog{{background:{C['bg2']};}}"
            f"QLabel{{color:{C['text']};}}"
            f"QLineEdit,QComboBox{{background:{C['surface']};border:1px solid {C['border']};"
            f"border-radius:7px;color:{C['text']};padding:5px 10px;font-size:12px;}}"
            f"QLineEdit:focus{{border-color:{C['purple']};}}"
            f"QComboBox QAbstractItemView{{background:{C['surface_h']};color:{C['text']};}}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 16)
        root.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("✦  Existence")
        title.setStyleSheet(f"color:{C['text']};font-size:18px;font-weight:600;")
        top.addWidget(title)
        top.addSpacing(24)
        self.tab_buttons: dict[str, QPushButton] = {}
        for key, label in self.TABS:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, k=key: self.show_tab(k))
            button.setStyleSheet(
                f"QPushButton{{background:transparent;color:{C['text2']};border:none;"
                f"border-bottom:2px solid transparent;padding:6px 14px;font-size:13px;}}"
                f"QPushButton:checked{{color:{C['text']};border-bottom-color:{C['purple']};}}"
                f"QPushButton:hover{{color:{C['text']};}}"
            )
            self.tab_buttons[key] = button
            top.addWidget(button)
        top.addStretch(1)
        root.addLayout(top)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{C['border']};")
        root.addWidget(line)

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {}
        self.pages["catalog"] = CatalogPage(hub)
        try:
            self.pages["resources"] = ResourcesPage()
        except Exception as exc:  # bibliothèque illisible : l'onglet l'explique
            fallback = QLabel(f"Ressources indisponibles : {exc}")
            fallback.setStyleSheet(f"color:{C['text2']};")
            self.pages["resources"] = fallback
        try:
            self.pages["wormholes"] = WormholesPage(hub)
        except Exception as exc:
            fallback = QLabel(f"Wormholes indisponibles : {exc}")
            fallback.setStyleSheet(f"color:{C['text2']};")
            self.pages["wormholes"] = fallback
        for key, _ in self.TABS:
            self.stack.addWidget(self.pages[key])
        root.addWidget(self.stack, 1)
        self.show_tab(tab)

    def refresh_modules(self) -> None:
        page = self.pages.get("catalog")
        if hasattr(page, "_after_hub_change"):
            page._after_hub_change()

    def show_tab(self, key: str) -> None:
        if key not in self.pages:
            key = "catalog"
        for name, button in self.tab_buttons.items():
            button.setChecked(name == key)
        self.stack.setCurrentWidget(self.pages[key])
        page = self.pages[key]
        if hasattr(page, "reload") and key == "resources":
            page.reload()


__all__ = ["ExistenceCenter", "load_catalog", "INSTALL_ROOT"]
