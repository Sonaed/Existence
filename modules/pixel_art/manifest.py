from modules.protocol import ModuleManifest


# Le module Pixel Art vit dans Existence ; Nebula charge son panneau quand
# il est branché sur son orbite (PIXEL/pixel_art.py côté Nebula).
MANIFEST = ModuleManifest(
    id="pixel_art",
    name="Pixel Art",
    version="26.0",
    module_type="existence_module",
    accepts=("image", "layer", "palette"),
    emits=("image", "palette"),
    resource_types=("palette", "image", "tileset"),
    host_capabilities=("raster_painting", "preview_surface"),
    host_universe="nebula",
    icon="▦",
    hosts=('nebula',),
    ui="dock",
)
