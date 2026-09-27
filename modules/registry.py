from .protocol import ModuleRegistry
from .fusion_creator import MANIFEST as FUSION_CREATOR_MANIFEST
from .resource_center import MANIFEST as RESOURCE_CENTER_MANIFEST
from .palette_creator import MANIFEST as PALETTE_CREATOR_MANIFEST
from .gradient_creator import MANIFEST as GRADIENT_CREATOR_MANIFEST
from .pixel_art import MANIFEST as PIXEL_ART_MANIFEST


def default_registry() -> ModuleRegistry:
    registry = ModuleRegistry()
    registry.register(FUSION_CREATOR_MANIFEST)
    registry.register(RESOURCE_CENTER_MANIFEST)
    registry.register(PALETTE_CREATOR_MANIFEST)
    registry.register(GRADIENT_CREATOR_MANIFEST)
    registry.register(PIXEL_ART_MANIFEST)
    return registry
