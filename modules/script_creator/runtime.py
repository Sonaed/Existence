"""Safe, dependency-free lifecycle for ``existence.user-script.v1`` resources.

The code intentionally has no knowledge of StarDust widgets.  Existence owns
validation, permission grants, durable versions, activation and execution.
"""
from __future__ import annotations

import ast
import copy
import io
import json
import multiprocessing
import queue
import re
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPT_FORMAT = "existence.user-script.v1"
SCRIPT_API_VERSION = "26.1"
ALLOWED_PERMISSIONS = frozenset({
    "document.read", "document.write", "resource.read", "resource.write",
    "catalog.read", "export.write", "ui.command",
})
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True)
class ScriptManifest:
    id: str
    name: str
    version: str
    hosts: tuple[str, ...]
    orbit_of: tuple[str, ...]
    entrypoint: str = "main.py"
    permissions: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    compatibility: dict[str, str] = field(default_factory=lambda: {"existence": SCRIPT_API_VERSION})
    commands: tuple[dict[str, Any], ...] = ()
    parameters: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ScriptManifest":
        return cls(str(value.get("id", "")), str(value.get("name", "")), str(value.get("version", "")),
                   tuple(value.get("hosts") or ()), tuple(value.get("orbit_of") or ()),
                   str(value.get("entrypoint", "main.py")), tuple(value.get("permissions") or ()),
                   tuple(value.get("capabilities") or ()), dict(value.get("compatibility") or {}),
                   tuple(value.get("commands") or ()), tuple(value.get("parameters") or ()))

    def to_dict(self) -> dict[str, Any]:
        return {"format": SCRIPT_FORMAT, "id": self.id, "name": self.name, "version": self.version,
                "creator": "user", "host_universe": "stardust", "hosts": list(self.hosts),
                "orbit_of": list(self.orbit_of), "entrypoint": self.entrypoint,
                "permissions": list(self.permissions), "capabilities": list(self.capabilities),
                "compatibility": dict(self.compatibility), "commands": [dict(x) for x in self.commands],
                "parameters": [dict(x) for x in self.parameters]}


@dataclass
class ScriptReport:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    logs: str = ""
    duration_ms: float = 0.0
    tested_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "errors": self.errors, "warnings": self.warnings,
                "logs": self.logs, "duration_ms": self.duration_ms, "tested_at": self.tested_at}


def validate_manifest(value: dict[str, Any], *, known_hosts: set[str] | None = None) -> ScriptReport:
    errors: list[str] = []
    if value.get("format") != SCRIPT_FORMAT:
        errors.append("format must be existence.user-script.v1")
    manifest = ScriptManifest.from_dict(value)
    if not _IDENTIFIER.fullmatch(manifest.id): errors.append("id must be a stable lowercase identifier")
    if not manifest.name.strip(): errors.append("name is required")
    if not re.fullmatch(r"\d+\.\d+\.\d+", manifest.version): errors.append("version must be semantic (x.y.z)")
    if manifest.entrypoint != "main.py": errors.append("only main.py is supported in the initial sandbox")
    if not manifest.hosts or not manifest.orbit_of: errors.append("hosts and orbit_of are required")
    if set(manifest.hosts) != set(manifest.orbit_of): errors.append("each script host must be an orbit target")
    if known_hosts and not set(manifest.hosts).issubset(known_hosts): errors.append("unknown target application")
    unknown = sorted(set(manifest.permissions) - ALLOWED_PERMISSIONS)
    if unknown: errors.append("permission refused: " + ", ".join(unknown))
    if not manifest.compatibility.get("existence"): errors.append("Existence API compatibility is required")
    if not all(isinstance(item, dict) and item.get("id") for item in manifest.commands):
        errors.append("each exposed command needs an id")
    return ScriptReport(not errors, errors)


def validate_source(source: str) -> ScriptReport:
    errors: list[str] = []
    try:
        tree = ast.parse(source, filename="main.py")
    except SyntaxError as exc:
        return ScriptReport(False, [f"syntax: {exc.msg} (line {exc.lineno})"])
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [part.name.split(".")[0] for part in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
            # v1 has no third-party dependencies and no import mechanism;
            # the target application's public API will arrive in ``context``.
            errors.append("imports are unavailable in the initial sandbox: " + ", ".join(names))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "open", "compile", "__import__"}:
            errors.append("restricted call: " + node.func.id)
    if not any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in tree.body):
        errors.append("main(context) function is required")
    return ScriptReport(not errors, errors)


class ScriptSandbox:
    """Deterministic in-memory test harness; it never grants system access."""
    _BUILTINS = {"abs": abs, "bool": bool, "dict": dict, "enumerate": enumerate, "float": float,
                 "int": int, "len": len, "list": list, "max": max, "min": min, "print": print,
                 "range": range, "str": str, "sum": sum, "tuple": tuple, "zip": zip}

    def run(self, manifest: dict[str, Any], source: str, *, timeout_ms: int = 1500) -> ScriptReport:
        report = validate_manifest(manifest)
        source_report = validate_source(source)
        report.errors.extend(source_report.errors)
        if report.errors:
            report.valid = False
            return report
        started = time.perf_counter()
        context = {"project": {"id": "test-project"}, "document": {"id": "test-document"},
                   "resources": [], "catalog": [], "exports": [], "commands": []}
        # ``fork`` avoids a public listener socket (the 3.14 default
        # forkserver is unavailable in confined desktop/package environments).
        process_context = multiprocessing.get_context("fork")
        results = process_context.Queue(1)
        worker = process_context.Process(target=_run_script, args=(source, context, results))
        worker.start(); worker.join(timeout_ms / 1000)
        if worker.is_alive():
            worker.terminate(); worker.join()
            report.errors.append("test timeout exceeded")
        else:
            try:
                outcome = results.get(timeout=0.2)
                report.logs = outcome["logs"]
                if outcome.get("error"):
                    report.errors.append("execution failed")
                    report.logs += outcome["error"]
                elif not outcome.get("json_result", False):
                    report.errors.append("main result must be JSON-compatible")
            except queue.Empty:
                report.errors.append("execution produced no report")
        report.duration_ms = round((time.perf_counter() - started) * 1000, 3)
        report.valid = not report.errors
        return report


def _run_script(source: str, context: dict[str, Any], results: Any) -> None:
    """Child-only execution boundary so a loop cannot freeze Existence."""
    output, errors = io.StringIO(), io.StringIO()
    namespace = {"__builtins__": ScriptSandbox._BUILTINS, "__name__": "user_script"}
    try:
        with redirect_stdout(output), redirect_stderr(errors):
            exec(compile(source, "main.py", "exec"), namespace, namespace)
            result = namespace["main"](copy.deepcopy(context))
        results.put({"logs": output.getvalue() + errors.getvalue(),
                     "json_result": result is None or isinstance(result, (dict, list, str, int, float, bool))})
    except Exception:
        results.put({"logs": output.getvalue() + errors.getvalue(), "error": traceback.format_exc()})


class ScriptPublisher:
    """Append-only Existence storage: resource://existence/user-scripts/<id>/vN."""
    def __init__(self, root: str | Path): self.root = Path(root)
    def publish(self, manifest: dict[str, Any], source: str, report: ScriptReport) -> dict[str, Any]:
        validation = validate_manifest(manifest)
        if validation.errors or not report.valid:
            raise ValueError("publication refused: " + "; ".join(validation.errors + report.errors))
        script_id = ScriptManifest.from_dict(manifest).id
        folder = self.root / script_id
        folder.mkdir(parents=True, exist_ok=True)
        versions = sorted(folder.glob("v*.json"))
        version = len(versions) + 1
        payload = {"manifest": copy.deepcopy(manifest), "source": source, "test_report": report.to_dict(),
                   "published_at": time.time(), "resource_uri": f"resource://existence/user-scripts/{script_id}/v{version}"}
        target = folder / f"v{version}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "current.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"version": version, "path": str(target), "uri": payload["resource_uri"]}


class ScriptLifecycle:
    """Installation, permission grants, activation and audited execution owned by Existence."""
    def __init__(self, publisher: ScriptPublisher):
        self.publisher, self._active, self._grants, self.logs = publisher, set(), {}, []
    def install(self, script_id: str) -> None:
        if not (self.publisher.root / script_id / "current.json").is_file(): raise KeyError(script_id)
    def authorize(self, script_id: str, permissions: list[str]) -> None:
        denied = set(permissions) - ALLOWED_PERMISSIONS
        if denied: raise PermissionError("permission refused: " + ", ".join(sorted(denied)))
        self._grants[script_id] = set(permissions)
    def activate(self, script_id: str) -> None:
        data = self._load(script_id); required = set(data["manifest"].get("permissions", []))
        if not required.issubset(self._grants.get(script_id, set())): raise PermissionError("permissions not granted")
        self._active.add(script_id)
    def deactivate(self, script_id: str) -> None: self._active.discard(script_id)
    def execute(self, script_id: str) -> ScriptReport:
        if script_id not in self._active: raise RuntimeError("script is inactive")
        data = self._load(script_id); report = ScriptSandbox().run(data["manifest"], data["source"])
        self.logs.append({"script_id": script_id, **report.to_dict()})
        return report
    def _load(self, script_id: str) -> dict[str, Any]:
        return json.loads((self.publisher.root / script_id / "current.json").read_text(encoding="utf-8"))
