from modules.protocol import ModuleManifest


MANIFEST = ModuleManifest(
    id="fusion_creator",
    name="Fusion Creator",
    version="26.0",
    module_type="existence_module",
    accepts=("fusion", "blend_result", "blend_definition", "image", "layer", "selection", "mask"),
    emits=("blend_result", "blend_definition"),
    resource_types=("blend_graph", "blend_preset", "image", "layer", "selection", "mask"),
    host_capabilities=("resource_provider", "composition_backend", "preview_surface"),
    hosts=('stardust', 'nebula'),
    ui="dock",
)
