"""Sonde de test GUI d'Existence — inactive sauf si ``EXISTENCE_TEST_PROBE`` est défini.

Chaque app lancée par le banc de test (tests_gui/smoke.py) :
* écrit son état toutes les 250 ms dans ``$EXISTENCE_TEST_PROBE/<app>.state.json``
  (menus, panneaux visibles, message de la barre d'état + état propre à l'app) ;
* exécute les commandes ajoutées dans ``$EXISTENCE_TEST_PROBE/<app>.cmd.jsonl``
  (une ligne JSON ``{"id": 3, "cmd": "send_layer", "args": [...]}``) et publie le
  résultat dans l'état (``results``).

Les commandes passent par le vrai code de l'app (mêmes méthodes que les menus) :
la sonde ne fait qu'observer et appuyer sur les boutons.
"""
from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path
from typing import Any, Callable

ENV = "EXISTENCE_TEST_PROBE"


def active() -> bool:
    return bool(os.environ.get(ENV))


def install_probe(window, app_id: str, state: Callable[[], dict] | None = None,
                  commands: dict[str, Callable[..., Any]] | None = None):
    folder = os.environ.get(ENV)
    if not folder:
        return None
    from PySide6.QtCore import QObject, QTimer
    from PySide6.QtWidgets import QDockWidget

    class Probe(QObject):
        def __init__(self) -> None:
            super().__init__(window)
            self.dir = Path(folder)
            self.dir.mkdir(parents=True, exist_ok=True)
            self.state_path = self.dir / f"{app_id}.state.json"
            self.cmd_path = self.dir / f"{app_id}.cmd.jsonl"
            self.offset = 0
            self.results: dict[str, Any] = {}
            self.timer = QTimer(self)
            self.timer.setInterval(250)
            self.timer.timeout.connect(self.tick)
            self.timer.start()

        def _menus(self) -> dict:
            out = {}
            try:
                for action in window.menuBar().actions():
                    menu = action.menu()
                    if menu is None:
                        continue
                    title = action.text().replace("&", "")
                    out[title] = {"visible": action.isVisible(),
                                  "items": [a.text() for a in menu.actions() if a.text()]}
            except RuntimeError:
                pass
            return out

        def _docks(self) -> list:
            docks = []
            for dock in window.findChildren(QDockWidget):
                try:
                    in_layout = window.dockWidgetArea(dock).value != 0
                except (RuntimeError, AttributeError):
                    in_layout = False
                docks.append({"name": dock.objectName(), "title": dock.windowTitle(),
                              "visible": dock.isVisible(), "in_layout": bool(in_layout),
                              "enabled": dock.isEnabled()})
            return docks

        def tick(self) -> None:
            self._read_commands()
            data = {"app": app_id, "pid": os.getpid(), "time": time.time(),
                    "menus": self._menus(), "docks": self._docks(), "results": self.results}
            try:
                data["status"] = window.statusBar().currentMessage()
            except RuntimeError:
                data["status"] = ""
            if state is not None:
                try:
                    data.update(state())
                except Exception as exc:  # noqa: BLE001
                    data["state_error"] = repr(exc)
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
            os.replace(tmp, self.state_path)

        def _read_commands(self) -> None:
            try:
                with open(self.cmd_path, encoding="utf-8") as handle:
                    handle.seek(self.offset)
                    lines = handle.readlines()
                    self.offset = handle.tell()
            except OSError:
                return
            for line in lines:
                try:
                    request = json.loads(line)
                except ValueError:
                    continue
                name = request.get("cmd", "")
                function = (commands or {}).get(name)
                if function is None:
                    self.results[str(request.get("id"))] = {"ok": False, "error": f"commande inconnue : {name}"}
                    continue
                try:
                    value = function(*request.get("args", []))
                    self.results[str(request.get("id"))] = {"ok": True, "value": value}
                except Exception as exc:  # noqa: BLE001
                    self.results[str(request.get("id"))] = {"ok": False, "error": repr(exc),
                                                            "trace": traceback.format_exc()[-1500:]}

    return Probe()


__all__ = ["install_probe", "active", "ENV"]
