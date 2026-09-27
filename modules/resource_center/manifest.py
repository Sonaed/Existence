from modules.protocol import ModuleManifest
from .catalog import RESOURCE_CATEGORIES


MANIFEST = ModuleManifest(
    id="resource_center",
    name="Resources",
    version="26.0",
    module_type="existence_module",
    accepts=("resource", "resource_bundle", "blend_definition", "blend_result"),
    emits=("resource", "resource_bundle", "blend_definition", "blend_result"),
    resource_types=tuple(RESOURCE_CATEGORIES),
    host_capabilities=("resource_store", "resource_provider", "resource_consumer", "bindable_to_universe"),
    hosts=(),
    ui="dock",
)
