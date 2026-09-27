"""Small, dependency-free protocol objects for Existence modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any


MODULE_ID_ALIASES = {
    "blend_creator": "fusion_creator",
    "blend-creator": "fusion_creator",
    "stellar_dust": "stardust",
    "stellar-dust": "stardust",
    "resource-center": "resource_center",
    "resource-centre": "resource_center",
    "palette-creator": "palette_creator",
    "gradient-creator": "gradient_creator",
}


def canonical_module_id(module_id: str) -> str:
    value = str(module_id).strip().casefold()
    return MODULE_ID_ALIASES.get(value, value)


@dataclass(frozen=True)
class ModuleManifest:
    id: str
    name: str
    version: str
    module_type: str
    entity_type: str = "module"
    availability: str = "available"
    activation: str = "inactive"
    ui_modes: tuple[str, ...] = ("dock", "panel", "floating", "tab", "contextual", "workspace")
    accepts: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()
    resource_types: tuple[str, ...] = ()
    host_capabilities: tuple[str, ...] = ()
    # Interface hébergeable (protocole existence.creator.v1) : Existence
    # possède le module ET son interface ; l'univers hôte la charge et s'y adapte.
    host_universe: str = ""          # univers qui peut héberger le module (ex. "stardust")
    interface: str = ""              # point d'entrée "paquet.module:fonction"
    interface_protocol: str = ""     # ex. "existence.creator.v1"
    produces: str = ""               # type de ressource produit
    file_extension: str = ""         # extension des documents du module (sans point)
    icon: str = ""
    # Univers capables d'héberger le module (Existence décide ; vide = selon host_universe).
    hosts: tuple[str, ...] = ()
    # Présentation dans l'hôte : "dock", "menu" ou "dock+menu".
    ui: str = "dock"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModuleSession:
    module_id: str
    host_id: str
    presentation: str = "dock"
    active: bool = False
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceBinding:
    """Explicit link between a shared resource kind and an ecosystem consumer."""

    resource_kind: str
    consumer_id: str
    access: str = "read"


class ModuleRegistry:
    """Registry owned by Existence; UI hosts remain free to choose placement."""

    def __init__(self) -> None:
        self._manifests: dict[str, ModuleManifest] = {}
        self._sessions: dict[tuple[str, str], ModuleSession] = {}
        self._resource_bindings: set[ResourceBinding] = set()

    def register(self, manifest: ModuleManifest) -> ModuleManifest:
        if manifest.id != canonical_module_id(manifest.id):
            manifest = replace(manifest, id=canonical_module_id(manifest.id))
        self._manifests[manifest.id] = manifest
        return manifest

    def manifest(self, module_id: str) -> ModuleManifest | None:
        return self._manifests.get(canonical_module_id(module_id))

    def manifests(self) -> list[ModuleManifest]:
        return list(self._manifests.values())

    def creators_for(self, host_id: str) -> list[ModuleManifest]:
        """Modules qui exposent une interface de Creator pour un univers hôte."""
        host_id = canonical_module_id(host_id)
        return [m for m in self._manifests.values()
                if m.interface and (m.host_universe == host_id or host_id in m.hosts)]

    def compatible(self, module_id: str, capabilities: dict[str, Any] | None = None) -> bool:
        manifest = self.manifest(module_id)
        if manifest is None:
            return False
        capabilities = capabilities or {}
        accepted = set(capabilities.get("accepts", ()))
        return not accepted or accepted.intersection(manifest.accepts)

    def open(self, module_id: str, host_id: str, presentation: str = "dock",
             context: dict[str, Any] | None = None) -> ModuleSession:
        module_id = canonical_module_id(module_id)
        if module_id not in self._manifests:
            raise KeyError(module_id)
        session = ModuleSession(module_id, host_id, presentation, True, context or {})
        self._sessions[(module_id, host_id)] = session
        return session

    def session(self, module_id: str, host_id: str) -> ModuleSession | None:
        return self._sessions.get((canonical_module_id(module_id), host_id))

    def bind_resource(self, resource_kind: str, consumer_id: str,
                      access: str = "read") -> ResourceBinding:
        if access not in {"read", "write", "read_write", "reference"}:
            raise ValueError(f"unsupported resource access: {access}")
        binding = ResourceBinding(resource_kind, canonical_module_id(consumer_id), access)
        self._resource_bindings.add(binding)
        return binding

    def unbind_resource(self, resource_kind: str, consumer_id: str) -> None:
        consumer_id = canonical_module_id(consumer_id)
        self._resource_bindings = {
            binding for binding in self._resource_bindings
            if not (binding.resource_kind == resource_kind and binding.consumer_id == consumer_id)
        }

    def resource_bindings(self, consumer_id: str | None = None) -> list[ResourceBinding]:
        bindings = self._resource_bindings
        if consumer_id is not None:
            consumer_id = canonical_module_id(consumer_id)
            bindings = {binding for binding in bindings if binding.consumer_id == consumer_id}
        return sorted(bindings, key=lambda item: (item.consumer_id, item.resource_kind))
