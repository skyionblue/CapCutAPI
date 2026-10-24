"""Transition metadata."""


class Transition_meta:
    """Transition metadata."""

    name: str
    """transition name"""
    is_vip: bool
    """whether this is a VIP feature"""

    resource_id: str
    """resource ID"""
    effect_id: str
    """effect ID"""
    md5: str

    default_duration: int
    """Default duration, in microseconds."""
    is_overlap: bool
    """Whether overlapping is allowed (uncertain)."""

    def __init__(self, name: str, is_vip: bool, resource_id: str, effect_id: str, md5: str, default_duration: float, is_overlap: bool):
        self.name = name
        self.is_vip = is_vip
        self.resource_id = resource_id
        self.effect_id = effect_id
        self.md5 = md5

        self.default_duration = int(round(default_duration * 1e6))
        self.is_overlap = is_overlap
