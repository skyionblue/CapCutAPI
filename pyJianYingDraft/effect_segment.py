"""Effect segment type."""

from typing import Union, Optional, List

from .time_util import Timerange
from .segment import Base_segment
from .video_segment import Video_effect

from .metadata import CapCut_Video_scene_effect_type, CapCut_Video_character_effect_type

class Effect_segment(Base_segment):
    """An effect segment, placed on its own effect track."""

    effect_inst: Video_effect
    """The effect material.

    Added to the material list automatically when placed on a track.
    """

    def __init__(self, effect_type: Union[CapCut_Video_scene_effect_type, CapCut_Video_character_effect_type],
                 target_timerange: Timerange, params: Optional[List[Optional[float]]] = None):
        self.effect_inst = Video_effect(effect_type, params, apply_target_type=2)  # global scope
        super().__init__(self.effect_inst.global_id, target_timerange)
