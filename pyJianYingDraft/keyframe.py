import uuid

from enum import Enum
from typing import Dict, List, Any

class Keyframe:
    """A single keyframe. Only linear interpolation is supported."""

    kf_id: str
    """Global keyframe id, generated automatically."""
    time_offset: int
    """Time offset from the start of the material."""
    values: List[float]
    """Keyframe values; in practice there is usually only one."""

    def __init__(self, time_offset: int, value: float):
        """Initialise a keyframe from a time offset and a value."""
        self.kf_id = uuid.uuid4().hex

        self.time_offset = time_offset
        self.values = [value]

    def export_json(self) -> Dict[str, Any]:
        return {
            # Defaults
            "curveType": "Line",
            "graphID": "",
            "left_control": {"x": 0.0, "y": 0.0},
            "right_control": {"x": 0.0, "y": 0.0},
            # Custom attributes
            "id": self.kf_id,
            "time_offset": self.time_offset,
            "values": self.values
        }

class Keyframe_property(Enum):
    """The property a keyframe list controls."""

    position_x = "KFTypePositionX"
    """Positive moves right. The value is the displayed value divided by the draft width, i.e. units of half the canvas width."""
    position_y = "KFTypePositionY"
    """Positive moves up. The value is the displayed value divided by the draft height, i.e. units of half the canvas height."""
    rotation = "KFTypeRotation"
    """Clockwise rotation, in **degrees**."""

    scale_x = "KFTypeScaleX"
    """Horizontal scale on its own (1.0 = unscaled). Mutually exclusive with `uniform_scale`."""
    scale_y = "KFTypeScaleY"
    """Vertical scale on its own (1.0 = unscaled). Mutually exclusive with `uniform_scale`."""
    uniform_scale = "UNIFORM_SCALE"
    """Scales both axes together (1.0 = unscaled). Mutually exclusive with `scale_x` and `scale_y`."""

    alpha = "KFTypeAlpha"
    """Opacity; 1.0 is fully opaque. `Video_segment` only."""
    saturation = "KFTypeSaturation"
    """Saturation; 0.0 is unchanged, range -1.0 to 1.0. `Video_segment` only."""
    contrast = "KFTypeContrast"
    """Contrast; 0.0 is unchanged, range -1.0 to 1.0. `Video_segment` only."""
    brightness = "KFTypeBrightness"
    """Brightness; 0.0 is unchanged, range -1.0 to 1.0. `Video_segment` only."""

    volume = "KFTypeVolume"
    """Volume; 1.0 is unchanged. `Audio_segment` and `Video_segment` only."""

class Keyframe_list:
    """A list of keyframes for one particular property."""

    list_id: str
    """Global id for the keyframe list, generated automatically."""
    keyframe_property: Keyframe_property
    """The property these keyframes control."""
    keyframes: List[Keyframe]
    """The keyframes."""

    def __init__(self, keyframe_property: Keyframe_property):
        """Initialise a keyframe list for the given property."""
        self.list_id = uuid.uuid4().hex

        self.keyframe_property = keyframe_property
        self.keyframes = []

    def add_keyframe(self, time_offset: int, value: float):
        """Add a keyframe to this list from a time offset and a value."""
        keyframe = Keyframe(time_offset, value)
        self.keyframes.append(keyframe)
        self.keyframes.sort(key=lambda x: x.time_offset)

    def export_json(self) -> Dict[str, Any]:
        return {
            "id": self.list_id,
            "keyframe_list": [kf.export_json() for kf in self.keyframes],
            "material_id": "",
            "property_type": self.keyframe_property.value
        }
