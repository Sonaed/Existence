"""Contrat commun Existence pour les manifests et l'état runtime.

Ce module ne force pas les univers à partager leur vocabulaire interne. Il
normalise uniquement ce qu'Existence doit comprendre pour les intégrer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import json
import subprocess
from pathlib import Path

# Formes de protocole actuellement comprises par Existence. Les manifests
# historiques utilisent deux chaînes et Nebula utilise un descripteur détaillé.
SUPPORTED_PROTOCOLS = {"existence.v1", "existence.contract.v1"}
CANONICAL_PROTOCOL = "existence.v1"


class FindingLevel(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"
    INCOMPATIBLE = "INCOMPATIBLE"


@dataclass(frozen=True)
class ContractFinding:
    level: FindingLevel
    code: str
    message: str
    field: str = ""


@dataclass
class ContractReport:
    identity: dict[str, Any] = field(default_factory=dict)
    findings: list[ContractFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(item.level in {FindingLevel.ERROR, FindingLevel.INCOMPATIBLE}
                       for item in self.findings)

    def add(self, level: FindingLevel, code: str, message: str, field: str = "") -> None:
        self.findings.append(ContractFinding(level, code, message, field))

    def counts(self) -> dict[str, int]:
        return {level.value: sum(item.level == level for item in self.findings)
                for level in FindingLevel}


CANONICAL_STATES = {"available", "loaded", "active", "closed", "error", "uninstalled"}
STATE_ALIASES = {
    "installed": "available",
    "ready": "available",
    "running": "active",
    "stopped": "closed",
    "failed": "error",
}


def map_lifecycle(value: Any) -> str:
    """Mappe un état applicatif vers le vocabulaire Existence."""
    state = str(value or "available").strip().casefold()
    return STATE_ALIASES.get(state, state if state in CANONICAL_STATES else "available")


def validate_manifest(
    manifest: dict[str, Any],
    *,
    expected_id: str | None = None,
    cached: dict[str, Any] | None = None,
    ecosystem_id: str = "existence",
) -> ContractReport:
    """Valide le sous-ensemble Existence réellement déclaré par un manifest."""
    report = ContractReport()
    if not isinstance(manifest, dict):
        report.add(FindingLevel.INCOMPATIBLE, "manifest.not_object", "Le manifest n'est pas un objet.")
        return report

    ident = manifest.get("id")
    report.identity = {"id": ident, "name": manifest.get("name"),
                       "version": manifest.get("version"),
                       "entity_type": manifest.get("entity_type") or manifest.get("app_kind") or manifest.get("kind")}
    if not ident or not manifest.get("name") or not manifest.get("version"):
        report.add(FindingLevel.ERROR, "identity.incomplete", "Identity incomplète : id, name et version sont requis.", "identity")
    else:
        report.add(FindingLevel.OK, "identity.valid", "Identity valide.", "identity")
    if expected_id and ident != expected_id:
        report.add(FindingLevel.INCOMPATIBLE, "identity.id_mismatch",
                   f"Identifiant reçu {ident!r}, attendu {expected_id!r}.", "id")

    entity_type = report.identity.get("entity_type")
    if entity_type not in {"universe", "module", "orbital_module", "service"}:
        report.add(FindingLevel.WARNING, "identity.entity_type_missing",
                   "entity_type/app_kind n'est pas déclaré explicitement.", "entity_type")
    else:
        report.add(FindingLevel.OK, "identity.entity_type_valid", "Type d'entité reconnu.", "entity_type")

    protocol = manifest.get("protocol")
    if protocol is None:
        report.add(FindingLevel.WARNING, "protocol.missing",
                   f"Aucune version de protocole déclarée ; utiliser {CANONICAL_PROTOCOL!r}.",
                   "protocol")
    elif isinstance(protocol, dict):
        if protocol.get("transport"):
            report.add(FindingLevel.OK, "protocol.descriptor",
                       "Protocole décrit par un descripteur de transport.", "protocol")
        else:
            report.add(FindingLevel.ERROR, "protocol.descriptor_incomplete",
                       "Descripteur de protocole sans champ 'transport'.", "protocol")
    elif str(protocol) in SUPPORTED_PROTOCOLS:
        report.add(FindingLevel.OK, "protocol.supported",
                   f"Protocole {protocol!r} pris en charge.", "protocol")
    else:
        report.add(FindingLevel.INCOMPATIBLE, "protocol.unsupported",
                   f"Protocole {protocol!r} inconnu ; attendu l'un de "
                   f"{sorted(SUPPORTED_PROTOCOLS)}.", "protocol")

    state = manifest.get("lifecycle_state", manifest.get("state"))
    if state is None:
        report.add(FindingLevel.WARNING, "lifecycle.missing", "Aucun état runtime déclaré.", "lifecycle")
    else:
        mapped = map_lifecycle(state)
        level = FindingLevel.OK if str(state).casefold() in CANONICAL_STATES else FindingLevel.WARNING
        report.add(level, "lifecycle.mapped", f"État {state!r} compris comme {mapped!r}.", "lifecycle")

    capabilities = manifest.get("capabilities")
    if isinstance(capabilities, list):
        report.add(FindingLevel.OK, "capabilities.declared", "Capabilities déclarées.", "capabilities")
    else:
        report.add(FindingLevel.WARNING, "capabilities.missing", "Aucune capability déclarée.", "capabilities")

    resources = manifest.get("resource_types", manifest.get("resources"))
    if resources is None:
        report.add(FindingLevel.WARNING, "resources.missing", "Aucune déclaration de ressources.", "resources")
    else:
        report.add(FindingLevel.OK, "resources.declared", "Ressources déclarées.", "resources")
        for resource in resources if isinstance(resources, list) else []:
            uri = resource.get("uri") if isinstance(resource, dict) else None
            if uri and uri.startswith("resource://") and not uri.startswith(f"resource://{ecosystem_id}/"):
                report.add(FindingLevel.ERROR, "resources.namespace_mismatch",
                           f"URI {uri!r} hors de l'espace {ecosystem_id!r}.", "resources")

    if isinstance(manifest.get("permissions"), list):
        report.add(FindingLevel.OK, "permissions.declared", "Permissions déclarées.", "permissions")
    else:
        report.add(FindingLevel.WARNING, "permissions.missing", "Permissions non déclarées.", "permissions")

    if manifest.get("protocol") or manifest.get("communications") or manifest.get("transport"):
        report.add(FindingLevel.OK, "transport.declared", "Transport ou protocole déclaré.", "transport")
    else:
        report.add(FindingLevel.WARNING, "transport.missing", "Transport non déclaré.", "transport")

    view = manifest.get("view")
    if isinstance(view, dict) or "embedding_mode" in manifest:
        report.add(FindingLevel.OK, "view.declared", "Surface de vue déclarée.", "view")
    else:
        report.add(FindingLevel.WARNING, "view.missing", "Aucune surface de vue déclarée.", "view")

    if cached and cached.get("version") and manifest.get("version") != cached.get("version"):
        report.add(FindingLevel.WARNING, "version.cache_mismatch",
                   f"Version runtime {manifest.get('version')} différente du catalogue {cached.get('version')}.", "version")
    return report


MANIFEST_OWNED_FIELDS = (
    "name", "version", "entity_type", "app_kind", "capabilities",
    "resource_types", "permissions", "accepted_messages", "emitted_messages",
    "dependencies", "resource_namespace", "embedding_mode", "view_protocol",
)


def load_manifest_file(path: str | Path) -> dict[str, Any] | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def load_manifest_command(command: list[str] | tuple[str, ...]) -> dict[str, Any] | None:
    try:
        result = subprocess.run(list(command), capture_output=True, text=True,
                                timeout=3, check=True)
        value = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def apply_manifest_to_catalog(app: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Injecte seulement les champs possédés par l'application."""
    for field in MANIFEST_OWNED_FIELDS:
        if field in manifest:
            app[field] = manifest[field]
    if manifest.get("kind") and not manifest.get("entity_type"):
        app["entity_type"] = manifest["kind"]
    if manifest.get("state") and not manifest.get("lifecycle_state"):
        app["observed_lifecycle_state"] = map_lifecycle(manifest["state"])
    app["manifest_loaded"] = True
    return app
