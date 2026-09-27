#!/usr/bin/env python3
"""Transport IPC réel d'Existence pour les univers indépendants.

Le protocole est volontairement minimal : une requête JSON par ligne, une
réponse JSON par ligne. Existence reste le médiateur : les endpoints ne se
connectent jamais directement entre eux.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass
class IPCResponse:
    ok: bool
    body: dict[str, Any]


class ProcessEndpoint:
    """Endpoint d'un processus Universe via stdin/stdout JSON-lines."""

    def __init__(self, command: list[str], *, cwd: Optional[str] = None, env: Optional[dict[str, str]] = None):
        self.command = command
        self.process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    @property
    def pid(self) -> int:
        return self.process.pid

    def request(self, message: str, **payload: Any) -> IPCResponse:
        if self.process.poll() is not None:
            raise RuntimeError(f"endpoint terminé avec le code {self.process.returncode}")
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("canal IPC indisponible")
        request_id = f"existence-{time.time_ns()}"
        request = {"protocol": "existence.ipc.v1", "request_id": request_id,
                   "message": message, "payload": payload}
        self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        raw = self.process.stdout.readline()
        if not raw:
            error = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"endpoint fermé sans réponse : {error[-500:]}")
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise RuntimeError("réponse IPC invalide")
        return IPCResponse(bool(body.get("ok")), body)

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.request("close")
            except (OSError, RuntimeError, ValueError):
                self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream is not None and not stream.closed:
                stream.close()


class ExistenceIPCRouter:
    """Médiateur entre plusieurs processus Universe."""

    def __init__(self, endpoints: Optional[dict[str, ProcessEndpoint]] = None):
        self.endpoints = endpoints or {}
        self.events: list[dict[str, Any]] = []

    def register(self, universe_id: str, endpoint: ProcessEndpoint) -> None:
        self.endpoints[universe_id] = endpoint

    def handshake_all(self) -> dict[str, dict[str, Any]]:
        manifests = {}
        for universe_id, endpoint in self.endpoints.items():
            response = endpoint.request("handshake")
            if not response.ok:
                raise RuntimeError(f"handshake refusé par {universe_id}: {response.body}")
            manifests[universe_id] = response.body.get("manifest", response.body)
            self.events.append({"type": "ipc.handshake", "universe": universe_id})
        return manifests

    def route(self, source: str, target: str, message: str, *, resource: str = "", **payload: Any) -> dict[str, Any]:
        """Valide le passage puis transmet réellement au processus cible."""
        endpoint = self.endpoints.get(target)
        if endpoint is None:
            raise RuntimeError(f"univers cible non connecté : {target}")
        body = dict(payload)
        if resource:
            body["resource"] = resource
        response = endpoint.request(message, **body)
        event = {
            "type": "message.routed",
            "source": source,
            "target": target,
            "message": message,
            "resource": resource,
            "transport": "process-json-lines",
            "ok": response.ok,
            "response": response.body,
        }
        self.events.append(event)
        if not response.ok:
            raise RuntimeError(f"{target} a refusé {message}: {response.body}")
        return event

    def close_all(self) -> None:
        for endpoint in list(self.endpoints.values()):
            endpoint.close()
