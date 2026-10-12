from modules.protocol import ModuleManifest
MANIFEST = ModuleManifest(
    id='texture_creator', name='Texture Creator', version='26.2.0', module_type='existence_module',
    accepts=('procedural_texture',), emits=('procedural_texture', 'image', 'vector', 'brush'),
    resource_types=('textures', 'brushes', 'procedural_texture'),
    host_capabilities=('creator_interface', 'resource_provider', 'preview_surface'),
    host_universe='stardust', interface='modules.texture_creator.interface:create_creator',
    interface_protocol='existence.creator.v1', produces='procedural_texture', file_extension='cstx',
    icon='▦', hosts=('stardust',), ui='dock', permissions=('resource.write','export.write'))
