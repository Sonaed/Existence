from modules.protocol import ModuleManifest


# Le module, son catalogue et les scripts publiés appartiennent à Existence.
# StarDust ne fait qu'héberger l'atelier de création lorsqu'il est en orbite.
MANIFEST = ModuleManifest(
    id="script_creator",
    name="Script Creator",
    version="26.1.0",
    module_type="existence_module",
    accepts=("script", "document", "catalog", "resource"),
    emits=("user_script",),
    resource_types=("user_script", "script_test_report"),
    host_capabilities=("creator_interface", "resource_provider", "script_authoring"),
    host_universe="stardust",
    interface="modules.script_creator.interface:create_creator",
    interface_protocol="existence.creator.v1",
    produces="user_script",
    file_extension="py",
    icon="⌘",
    hosts=("stardust",),
    ui="dock",
    api_version="26.1",
    permissions=("document.read", "document.write", "resource.read", "resource.write",
                 "catalog.read", "export.write", "ui.command"),
)
