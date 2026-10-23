"""Video mask metadata."""


class Mask_meta:
    """Mask metadata."""

    name: str
    """transition name"""

    resource_type: str
    """Resource type, tied to the mask shape."""

    resource_id: str
    """resource ID"""
    effect_id: str
    """effect ID"""
    md5: str

    default_aspect_ratio: float
    """Default aspect ratio; width and height are both relative to the material."""

    def __init__(self, name: str, resource_type: str, resource_id: str, effect_id: str, md5: str, default_aspect_ratio: float):
        self.name = name
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.effect_id = effect_id
        self.md5 = md5

        self.default_aspect_ratio = default_aspect_ratio
