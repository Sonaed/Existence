from .protocol import ModuleRegistry
from .texture_creator import MANIFEST as TEXTURE_CREATOR_MANIFEST
from .fusion_creator import MANIFEST as FUSION_CREATOR_MANIFEST
from .resource_center import MANIFEST as RESOURCE_CENTER_MANIFEST
from .palette_creator import MANIFEST as PALETTE_CREATOR_MANIFEST
from .gradient_creator import MANIFEST as GRADIENT_CREATOR_MANIFEST
from .pixel_art import MANIFEST as PIXEL_ART_MANIFEST
from .script_creator import MANIFEST as SCRIPT_CREATOR_MANIFEST


def default_registry() -> ModuleRegistry:
    registry = ModuleRegistry()
    registry.register(FUSION_CREATOR_MANIFEST)
    registry.register(RESOURCE_CENTER_MANIFEST)
    registry.register(PALETTE_CREATOR_MANIFEST)
    registry.register(GRADIENT_CREATOR_MANIFEST)
    registry.register(PIXEL_ART_MANIFEST)
    registry.register(SCRIPT_CREATOR_MANIFEST)
    registry.register(TEXTURE_CREATOR_MANIFEST)
    return registry
