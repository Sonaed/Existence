"""SDK d'hôte Existence : n'importe quelle app Qt accueille les modules branchés sur elle.

Usage dans une app (après la création de la barre de menus)::

    from modules.host_sdk import install_module_host
    host = install_module_host(window, "nova",
                               register_dock=lambda dock: ...,      # facultatif : menu Panneaux de l'app
                               handled={"pixel_art"},               # modules que l'app gère elle-même
                               image_provider=lambda: png_bytes)    # facultatif : image courante

L'hôte :
* ajoute un menu « Modules » juste après « Édition » (ou « Fichier ») ;
* crée un panneau (QDockWidget) pour chaque module qui fournit une interface
  (protocole ``existence.creator.v1``) et l'ajoute au menu Modules + au menu
  des panneaux de l'app (``register_dock``) ;
* ajoute les actions des modules applicatifs (Nova, Singularity…) : ouvrir,
  envoyer l'image courante par wormhole ;
* relit Existence toutes les 2 s : un module branché / débranché sur la
  carte apparaît / disparaît sans redémarrer.

Existence décide de la compatibilité (``modules.compat``) ; l'hôte ne fait
qu'afficher ce qu'on lui a branché.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QDockWidget, QMenu, QMessageBox, QTabWidget, QWidget

from modules.compat import APPS_JSON, load_apps, plugged_modules

MENU_TITLE = "Modules"


def _find_menu(menubar, titles: Iterable[str]):
    wanted = {t.replace("&", "").lower() for t in titles}
    for action in menubar.actions():
        if action.menu() is not None and action.text().replace("&", "").lower() in wanted:
            return action
    return None


class ModuleHost(QObject):
    def __init__(self, window, host_id: str, register_dock: Callable | None = None,
                 handled: Iterable[str] = (), image_provider: Callable[[], bytes] | None = None,
                 theme: dict | None = None) -> None:
        super().__init__(window)
        self.window = window
        self.host_id = host_id
        self.register_dock = register_dock
        self.handled = set(handled)
        self.image_provider = image_provider
        self.theme = theme or {}
        self.docks: dict[str, QDockWidget] = {}
        self.creators: dict[str, Any] = {}
        self.active: list[dict] = []
        self._stamp = None
        self._registered: set[int] = set()
        self.menu = QMenu(MENU_TITLE, window)
        self.menu.aboutToShow.connect(self._fill_menu)
        menubar = window.menuBar()
        after = _find_menu(menubar, ("Édition", "Edition", "Edit"))
        if after is None:
            after = _find_menu(menubar, ("Fichier", "File"))
        actions = menubar.actions()
        if after is not None and after in actions and actions.index(after) + 1 < len(actions):
            menubar.insertMenu(actions[actions.index(after) + 1], self.menu)
        else:
            menubar.addMenu(self.menu)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.sync)
        self.timer.start()
        QTimer.singleShot(0, self.sync)

    # ── état Existence ──
    def _changed(self) -> bool:
        try:
            stamp = APPS_JSON.stat().st_mtime
        except OSError:
            stamp = 0
        if stamp == self._stamp:
            return False
        self._stamp = stamp
        return True

    def sync(self, force: bool = False) -> None:
        if not self._changed() and not force:
            return
        apps = load_apps()
        self.active = [m for m in plugged_modules(self.host_id, apps) if m.get("id") not in self.handled]
        wanted = {m["id"] for m in self.active}
        for module_id in list(self.docks):
            if module_id not in wanted:
                self._remove_dock(module_id)
        for module in self.active:
            manifest = self._manifest(module["id"])
            if manifest is not None and manifest.interface and "dock" in (manifest.ui or "dock"):
                if module["id"] not in self.docks:
                    self._add_dock(module, manifest)
        self.menu.menuAction().setVisible(bool(self.active))

    @staticmethod
    def _manifest(module_id: str):
        try:
            from modules.registry import default_registry
            return default_registry().manifest(module_id)
        except Exception:  # noqa: BLE001
            return None

    # ── panneaux ──
    def _add_dock(self, module: dict, manifest) -> None:
        try:
            from modules.creator_interface import create_creator
            creator = create_creator(manifest, {"host_id": self.host_id, "theme": self.theme})
            edit = creator.edit_widget()
            test = creator.test_widget() if hasattr(creator, "test_widget") else None
        except Exception as exc:  # noqa: BLE001 — un module cassé ne fait pas tomber l'hôte
            print(f"[{self.host_id}] module {module['id']} indisponible : {exc}", file=sys.stderr)
            return
        content: QWidget = edit
        if test is not None:
            tabs = QTabWidget()
            tabs.addTab(edit, "Édition")
            tabs.addTab(test, "Aperçu")
            content = tabs
        dock = QDockWidget(f"{manifest.icon or '◇'} {module.get('name') or manifest.name}", self.window)
        dock.setObjectName(f"existence_module_{module['id']}")
        dock.setWidget(content)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.docks[module["id"]] = dock
        self.creators[module["id"]] = creator
        if self.register_dock is not None and id(dock) not in self._registered:
            try:
                self.register_dock(dock)
                self._registered.add(id(dock))
            except Exception:  # noqa: BLE001
                pass

    def _remove_dock(self, module_id: str) -> None:
        dock = self.docks.pop(module_id)
        self.creators.pop(module_id, None)
        try:
            action = dock.toggleViewAction()
            for widget in action.associatedObjects() if hasattr(action, "associatedObjects") else ():
                if isinstance(widget, QMenu):
                    widget.removeAction(action)
            dock.hide()
            self.window.removeDockWidget(dock)
            dock.deleteLater()
        except RuntimeError:
            pass

    # ── menu Modules ──
    def _fill_menu(self) -> None:
        menu = self.menu
        menu.clear()
        if not self.active:
            empty = menu.addAction("Aucun module branché — branche-en un depuis Existence")
            empty.setEnabled(False)
            return
        for module in self.active:
            module_id = module["id"]
            name = module.get("name", module_id)
            icon = module.get("icon_emoji", "◇")
            if module_id in self.docks:
                action = self.docks[module_id].toggleViewAction()
                action.setText(f"{icon}  {name}")
                menu.addAction(action)
                creator = self.creators.get(module_id)
                if creator is not None and hasattr(creator, "library_export"):
                    menu.addAction(f"      Publier « {name} » dans les Ressources…",
                                   lambda m=module_id: self._publish(m))
            elif module.get("exec_path"):
                sub = menu.addMenu(f"{icon}  {name}")
                sub.addAction(f"Ouvrir {name}", lambda m=module: self._launch(m))
                if self.image_provider is not None:
                    sub.addAction("Envoyer l'image vers " + name, lambda m=module: self._send(m, live=False))
                    if module_id in {"nova", "nebula"}:
                        sub.addAction("Lier l'image en direct avec " + name, lambda m=module: self._send(m, live=True))
            else:
                action = menu.addAction(f"{icon}  {name}")
                action.setEnabled(False)
                action.setToolTip("Ce module n'a pas d'interface pour cette app.")
        menu.addSeparator()
        menu.addAction("Gérer les modules dans Existence…", self._open_existence)

    def _publish(self, module_id: str) -> None:
        from PySide6.QtWidgets import QInputDialog
        creator = self.creators.get(module_id)
        if creator is None:
            return
        name, ok = QInputDialog.getText(self.window, "Publier", "Nom de la ressource :",
                                        text=getattr(creator, "default_name", "Sans titre"))
        if not ok or not name.strip():
            return
        try:
            kind, payload, apps = creator.library_export(name.strip())
            from modules.resource_center.library import SharedLibrary
            SharedLibrary().add_json(kind, name.strip(), payload, apps=apps, owner=self.host_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self.window, "Publier", f"Impossible : {exc}")
            return
        self.window.statusBar().showMessage(f"« {name.strip()} » publié dans les Ressources", 4000)

    def _launch(self, module: dict) -> None:
        exec_path = module.get("exec_path")
        if not exec_path:
            return
        try:
            subprocess.Popen([exec_path, *module.get("exec_args", [])],
                             cwd=module.get("working_dir") or None, start_new_session=True)
        except OSError as exc:
            QMessageBox.warning(self.window, module.get("name", ""), f"Lancement impossible : {exc}")

    def _send(self, module: dict, live: bool) -> None:
        try:
            from modules.wormhole import Wormhole
            data = self.image_provider()
            if not data:
                return
            Wormhole(self.host_id).send(module["id"], data=data, name="image.png", live=live)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self.window, "Wormhole", f"Envoi impossible : {exc}")
            return
        self.window.statusBar().showMessage(f"⇄ Envoyé vers {module.get('name', module['id'])}", 4000)

    def _open_existence(self) -> None:
        QMessageBox.information(self.window, "Modules",
                                "Branche, débranche ou range les modules sur la carte d'Existence "
                                "(glisser un module sur une app, ou dans la boîte à outils).\n\n"
                                "Cette app se met à jour toute seule.")


def install_module_host(window, host_id: str, **kwargs) -> ModuleHost | None:
    try:
        return ModuleHost(window, host_id, **kwargs)
    except Exception as exc:  # noqa: BLE001
        print(f"[{host_id}] hôte de modules indisponible : {exc}", file=sys.stderr)
        return None


def load_sdk(existence_root: str | None = None):
    """Aide pour les apps : rend ``modules`` importable depuis le dossier Existence."""
    root = Path(existence_root or os.environ.get("EXISTENCE_ROOT", "") or
                ("/usr/share/existence/existence" if Path("/usr/share/existence/existence").is_dir()
                 else str(Path.home() / "Documents" / "Existence")))
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from modules import host_sdk
    return host_sdk


__all__ = ["ModuleHost", "install_module_host", "load_sdk", "MENU_TITLE"]
