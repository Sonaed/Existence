from modules.protocol import ModuleManifest


MANIFEST = ModuleManifest(
    id="palette_creator",
    name="Palette Creator",
    version="26.0",
    module_type="existence_module",
    accepts=("palette", "color", "image"),
    emits=("palette",),
    resource_types=("palette", "palettes"),
    host_capabilities=("creator_interface", "resource_provider", "preview_surface"),
    host_universe="stardust",
    interface="modules.palette_creator.interface:create_creator",
    interface_protocol="existence.creator.v1",
    produces="palette",
    file_extension="cspl",
    icon="◐",
    hosts=('stardust', 'nebula'),
    ui="dock",
)
