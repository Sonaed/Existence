from modules.protocol import ModuleManifest


MANIFEST = ModuleManifest(
    id="gradient_creator",
    name="Gradient Creator",
    version="26.0",
    module_type="existence_module",
    accepts=("gradient", "palette", "color"),
    emits=("gradient",),
    resource_types=("gradient", "gradients"),
    host_capabilities=("creator_interface", "resource_provider", "preview_surface"),
    host_universe="stardust",
    interface="modules.gradient_creator.interface:create_creator",
    interface_protocol="existence.creator.v1",
    produces="gradient",
    file_extension="csgr",
    icon="◑",
    hosts=('stardust', 'nebula'),
    ui="dock",
)
