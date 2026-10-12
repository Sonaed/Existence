"""Small StarDust-facing editor. Runtime ownership stays in :mod:`runtime`."""
from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from .runtime import SCRIPT_FORMAT, ScriptSandbox, validate_manifest, validate_source

_TEMPLATE = '''def main(context):
    """Run against the public API supplied by the target application."""
    print("Script test: ", context["project"]["id"])
    return {"status": "ok"}
'''


class ScriptCreatorInterface(QWidget):
    changed = Signal()
    default_name = "Untitled Script"

    def __init__(self, host: dict):
        super().__init__()
        self._host = host
        self._manifest = {"format": SCRIPT_FORMAT, "id": "user.untitled-script", "name": self.default_name,
                          "version": "1.0.0", "creator": "user", "host_universe": "stardust",
                          "hosts": ["nova"], "orbit_of": ["nova"], "entrypoint": "main.py",
                          "permissions": ["catalog.read"], "capabilities": ["nova.catalog.query"],
                          "compatibility": {"existence": "26.1", "nova": "26.1"},
                          "commands": [{"id": "run", "label": "Run script"}], "parameters": []}
        self._source = _TEMPLATE
        self._history: list[tuple[dict, str]] = []
        self._redo: list[tuple[dict, str]] = []
        self._widget = self._build()

    def _build(self):
        root, form = QWidget(), QFormLayout()
        self.name = QLineEdit(self._manifest["name"])
        self.script_id = QLineEdit(self._manifest["id"])
        self.hosts = QLineEdit("nova")
        self.permissions = QLineEdit("catalog.read")
        self.source = QPlainTextEdit(self._source)
        self.source.setMinimumHeight(260)
        for widget in (self.name, self.script_id, self.hosts, self.permissions, self.source):
            widget.textChanged.connect(self._changed)
        form.addRow("Name", self.name); form.addRow("Identifier", self.script_id)
        form.addRow("Target application", self.hosts); form.addRow("Permissions", self.permissions)
        layout = QVBoxLayout(root); layout.addLayout(form); layout.addWidget(QLabel("main.py")); layout.addWidget(self.source)
        return root

    def _changed(self): self.changed.emit()
    def edit_widget(self): return self._widget
    def test_widget(self): return None
    def snapshot(self):
        data = dict(self._manifest)
        data.update({"id": self.script_id.text().strip(), "name": self.name.text().strip(),
                     "hosts": [x.strip() for x in self.hosts.text().split(",") if x.strip()],
                     "orbit_of": [x.strip() for x in self.hosts.text().split(",") if x.strip()],
                     "permissions": [x.strip() for x in self.permissions.text().split(",") if x.strip()]})
        return {"manifest": data, "source": self.source.toPlainText()}
    def load(self, data):
        payload = data.get("manifest", data); self._manifest = dict(payload)
        self.name.setText(self._manifest.get("name", self.default_name)); self.script_id.setText(self._manifest.get("id", ""))
        self.hosts.setText(", ".join(self._manifest.get("hosts", []))); self.permissions.setText(", ".join(self._manifest.get("permissions", [])))
        self.source.setPlainText(data.get("source", _TEMPLATE)); self.changed.emit()
    def validate(self):
        snap = self.snapshot(); report = validate_manifest(snap["manifest"]); source = validate_source(snap["source"])
        return [("error", error) for error in report.errors + source.errors]
    def resource_payload(self):
        snap = self.snapshot(); report = ScriptSandbox().run(snap["manifest"], snap["source"])
        return {"kind": "user_script", "manifest": snap["manifest"], "source": snap["source"], "test_report": report.to_dict()}
    def undo(self):
        if self._history:
            self._redo.append((self._manifest, self._source)); manifest, source = self._history.pop(); self.load({"manifest": manifest, "source": source})
    def redo(self):
        if self._redo:
            self._history.append((self._manifest, self._source)); manifest, source = self._redo.pop(); self.load({"manifest": manifest, "source": source})


def create_creator(host: dict) -> ScriptCreatorInterface:
    return ScriptCreatorInterface(host)
